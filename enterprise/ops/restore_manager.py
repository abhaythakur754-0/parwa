# Restore Manager - Week 50 Builder 4
# Restore operations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid


class RestoreStatus(Enum):
    PENDING = "pending"
    VALIDATING = "validating"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class RestorePoint:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    backup_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    data_snapshot: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RestoreOperation:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    backup_id: str = ""
    target_location: str = ""
    status: RestoreStatus = RestoreStatus.PENDING
    validate_before_restore: bool = True
    pre_restore_snapshot_id: Optional[str] = None
    progress_percent: int = 0
    items_restored: int = 0
    total_items: int = 0
    error_message: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


class RestoreManager:
    """Manages restore operations"""

    def __init__(self):
        self._restore_points: Dict[str, RestorePoint] = {}
        self._operations: Dict[str, RestoreOperation] = {}
        self._metrics = {
            "total_restores": 0,
            "successful": 0,
            "failed": 0,
            "rolled_back": 0
        }

    def create_restore_point(
        self,
        name: str,
        backup_id: str,
        data_snapshot: Optional[Dict[str, Any]] = None
    ) -> RestorePoint:
        """Create a restore point before restore"""
        point = RestorePoint(
            name=name,
            backup_id=backup_id,
            data_snapshot=data_snapshot or {}
        )
        self._restore_points[point.id] = point
        return point

    def initiate_restore(
        self,
        backup_id: str,
        target_location: str,
        validate_before_restore: bool = True
    ) -> RestoreOperation:
        """Initiate a restore operation"""
        operation = RestoreOperation(
            backup_id=backup_id,
            target_location=target_location,
            validate_before_restore=validate_before_restore
        )
        self._operations[operation.id] = operation
        self._metrics["total_restores"] += 1
        return operation

    def start_restore(self, operation_id: str) -> bool:
        """Start a restore operation"""
        operation = self._operations.get(operation_id)
        if not operation or operation.status != RestoreStatus.PENDING:
            return False

        # Create pre-restore snapshot
        restore_point = self.create_restore_point(
            name=f"pre_restore_{operation_id}",
            backup_id=operation.backup_id
        )
        operation.pre_restore_snapshot_id = restore_point.id

        if operation.validate_before_restore:
            operation.status = RestoreStatus.VALIDATING
        else:
            operation.status = RestoreStatus.IN_PROGRESS

        operation.started_at = datetime.utcnow()
        return True

    def validate_complete(self, operation_id: str, success: bool) -> bool:
        """Complete validation phase"""
        operation = self._operations.get(operation_id)
        if not operation or operation.status != RestoreStatus.VALIDATING:
            return False

        if success:
            operation.status = RestoreStatus.IN_PROGRESS
        else:
            operation.status = RestoreStatus.FAILED
            operation.error_message = "Validation failed"
            self._metrics["failed"] += 1

        return True

    def update_progress(
        self,
        operation_id: str,
        items_restored: int,
        total_items: int
    ) -> bool:
        """Update restore progress"""
        operation = self._operations.get(operation_id)
        if not operation or operation.status != RestoreStatus.IN_PROGRESS:
            return False

        operation.items_restored = items_restored
        operation.total_items = total_items
        operation.progress_percent = int((items_restored / total_items * 100) if total_items > 0 else 0)
        return True

    def complete_restore(self, operation_id: str) -> bool:
        """Complete a restore operation"""
        operation = self._operations.get(operation_id)
        if not operation or operation.status != RestoreStatus.IN_PROGRESS:
            return False

        operation.status = RestoreStatus.COMPLETED
        operation.progress_percent = 100
        operation.completed_at = datetime.utcnow()
        self._metrics["successful"] += 1
        return True

    def fail_restore(self, operation_id: str, error_message: str = "") -> bool:
        """Mark restore as failed"""
        operation = self._operations.get(operation_id)
        if not operation:
            return False

        operation.status = RestoreStatus.FAILED
        operation.error_message = error_message
        self._metrics["failed"] += 1
        return True

    def rollback_restore(self, operation_id: str) -> bool:
        """Rollback a restore using pre-restore snapshot"""
        operation = self._operations.get(operation_id)
        if not operation or not operation.pre_restore_snapshot_id:
            return False

        operation.status = RestoreStatus.ROLLED_BACK
        operation.completed_at = datetime.utcnow()
        self._metrics["rolled_back"] += 1
        return True

    def get_operation(self, operation_id: str) -> Optional[RestoreOperation]:
        """Get operation by ID"""
        return self._operations.get(operation_id)

    def get_restore_point(self, point_id: str) -> Optional[RestorePoint]:
        """Get restore point by ID"""
        return self._restore_points.get(point_id)

    def get_operations_by_backup(self, backup_id: str) -> List[RestoreOperation]:
        """Get all operations for a backup"""
        return [o for o in self._operations.values() if o.backup_id == backup_id]

    def get_active_operations(self) -> List[RestoreOperation]:
        """Get all active operations"""
        active_statuses = [RestoreStatus.PENDING, RestoreStatus.VALIDATING, RestoreStatus.IN_PROGRESS]
        return [o for o in self._operations.values() if o.status in active_statuses]

    def cancel_operation(self, operation_id: str) -> bool:
        """Cancel a pending operation"""
        operation = self._operations.get(operation_id)
        if not operation or operation.status != RestoreStatus.PENDING:
            return False
        operation.status = RestoreStatus.FAILED
        operation.error_message = "Cancelled by user"
        return True

    def get_metrics(self) -> Dict[str, Any]:
        return self._metrics.copy()
