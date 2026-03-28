# Backup Manager - Week 50 Builder 4
# Backup automation

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import uuid


class BackupType(Enum):
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"


class BackupStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class BackupSchedule:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    backup_type: BackupType = BackupType.FULL
    interval_hours: int = 24
    retention_days: int = 30
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Backup:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    schedule_id: str = ""
    backup_type: BackupType = BackupType.FULL
    status: BackupStatus = BackupStatus.PENDING
    size_bytes: int = 0
    location: str = ""
    checksum: str = ""
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


class BackupManager:
    """Manages backup automation"""

    def __init__(self):
        self._schedules: Dict[str, BackupSchedule] = {}
        self._backups: Dict[str, Backup] = {}
        self._metrics = {
            "total_backups": 0,
            "successful": 0,
            "failed": 0,
            "total_size_bytes": 0
        }

    def create_schedule(
        self,
        name: str,
        backup_type: BackupType,
        interval_hours: int = 24,
        retention_days: int = 30
    ) -> BackupSchedule:
        """Create a backup schedule"""
        schedule = BackupSchedule(
            name=name,
            backup_type=backup_type,
            interval_hours=interval_hours,
            retention_days=retention_days,
            next_run=datetime.utcnow()
        )
        self._schedules[schedule.id] = schedule
        return schedule

    def create_backup(
        self,
        schedule_id: str,
        backup_type: BackupType,
        location: str = ""
    ) -> Backup:
        """Create a backup"""
        backup = Backup(
            schedule_id=schedule_id,
            backup_type=backup_type,
            location=location
        )
        self._backups[backup.id] = backup
        self._metrics["total_backups"] += 1
        return backup

    def start_backup(self, backup_id: str) -> bool:
        """Start a backup"""
        backup = self._backups.get(backup_id)
        if not backup or backup.status != BackupStatus.PENDING:
            return False
        backup.status = BackupStatus.IN_PROGRESS
        backup.started_at = datetime.utcnow()
        return True

    def complete_backup(
        self,
        backup_id: str,
        size_bytes: int,
        checksum: str = ""
    ) -> bool:
        """Complete a backup"""
        backup = self._backups.get(backup_id)
        if not backup or backup.status != BackupStatus.IN_PROGRESS:
            return False
        backup.status = BackupStatus.COMPLETED
        backup.completed_at = datetime.utcnow()
        backup.size_bytes = size_bytes
        backup.checksum = checksum

        # Set expiration
        schedule = self._schedules.get(backup.schedule_id)
        if schedule:
            backup.expires_at = datetime.utcnow() + timedelta(days=schedule.retention_days)

        self._metrics["successful"] += 1
        self._metrics["total_size_bytes"] += size_bytes

        # Update schedule
        if schedule:
            schedule.last_run = datetime.utcnow()
            schedule.next_run = datetime.utcnow() + timedelta(hours=schedule.interval_hours)

        return True

    def fail_backup(self, backup_id: str) -> bool:
        """Mark backup as failed"""
        backup = self._backups.get(backup_id)
        if not backup:
            return False
        backup.status = BackupStatus.FAILED
        self._metrics["failed"] += 1
        return True

    def get_backup(self, backup_id: str) -> Optional[Backup]:
        """Get backup by ID"""
        return self._backups.get(backup_id)

    def get_schedule(self, schedule_id: str) -> Optional[BackupSchedule]:
        """Get schedule by ID"""
        return self._schedules.get(schedule_id)

    def get_backups_by_schedule(self, schedule_id: str) -> List[Backup]:
        """Get all backups for a schedule"""
        return [b for b in self._backups.values() if b.schedule_id == schedule_id]

    def get_due_schedules(self) -> List[BackupSchedule]:
        """Get schedules due for backup"""
        now = datetime.utcnow()
        return [
            s for s in self._schedules.values()
            if s.enabled and s.next_run and s.next_run <= now
        ]

    def get_expired_backups(self) -> List[Backup]:
        """Get expired backups for cleanup"""
        now = datetime.utcnow()
        return [
            b for b in self._backups.values()
            if b.expires_at and b.expires_at < now and b.status == BackupStatus.COMPLETED
        ]

    def mark_expired(self, backup_id: str) -> bool:
        """Mark backup as expired"""
        backup = self._backups.get(backup_id)
        if not backup:
            return False
        backup.status = BackupStatus.EXPIRED
        return True

    def delete_backup(self, backup_id: str) -> bool:
        """Delete a backup record"""
        if backup_id in self._backups:
            del self._backups[backup_id]
            return True
        return False

    def enable_schedule(self, schedule_id: str) -> bool:
        """Enable a schedule"""
        schedule = self._schedules.get(schedule_id)
        if not schedule:
            return False
        schedule.enabled = True
        return True

    def disable_schedule(self, schedule_id: str) -> bool:
        """Disable a schedule"""
        schedule = self._schedules.get(schedule_id)
        if not schedule:
            return False
        schedule.enabled = False
        return True

    def get_metrics(self) -> Dict[str, Any]:
        return self._metrics.copy()

    def cleanup_expired(self) -> int:
        """Remove expired backup records"""
        expired = self.get_expired_backups()
        for backup in expired:
            self.mark_expired(backup.id)
        return len(expired)
