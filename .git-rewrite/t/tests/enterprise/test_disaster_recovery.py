# Tests for Builder 4 - Disaster Recovery
# Week 50: backup_manager.py, restore_manager.py, failover_manager.py

import pytest
from datetime import datetime, timedelta
import time

from enterprise.ops.backup_manager import (
    BackupManager, Backup, BackupSchedule, BackupType, BackupStatus
)
from enterprise.ops.restore_manager import (
    RestoreManager, RestoreOperation, RestorePoint, RestoreStatus
)
from enterprise.ops.failover_manager import (
    FailoverManager, Region, FailoverEvent, FailoverStatus, RegionStatus
)


# =============================================================================
# BACKUP MANAGER TESTS
# =============================================================================

class TestBackupManager:
    """Tests for BackupManager class"""

    def test_init(self):
        """Test manager initialization"""
        manager = BackupManager()
        assert manager is not None
        metrics = manager.get_metrics()
        assert metrics["total_backups"] == 0

    def test_create_schedule(self):
        """Test creating a backup schedule"""
        manager = BackupManager()
        schedule = manager.create_schedule(
            name="daily_backup",
            backup_type=BackupType.FULL,
            interval_hours=24,
            retention_days=30
        )
        assert schedule.name == "daily_backup"
        assert schedule.backup_type == BackupType.FULL
        assert schedule.interval_hours == 24
        assert schedule.enabled is True

    def test_create_backup(self):
        """Test creating a backup"""
        manager = BackupManager()
        schedule = manager.create_schedule("daily", BackupType.FULL)
        backup = manager.create_backup(
            schedule_id=schedule.id,
            backup_type=BackupType.FULL,
            location="s3://backups/backup_001"
        )
        assert backup.status == BackupStatus.PENDING
        assert backup.backup_type == BackupType.FULL

    def test_start_backup(self):
        """Test starting a backup"""
        manager = BackupManager()
        schedule = manager.create_schedule("daily", BackupType.FULL)
        backup = manager.create_backup(schedule.id, BackupType.FULL)
        result = manager.start_backup(backup.id)
        assert result is True
        assert backup.status == BackupStatus.IN_PROGRESS
        assert backup.started_at is not None

    def test_complete_backup(self):
        """Test completing a backup"""
        manager = BackupManager()
        schedule = manager.create_schedule("daily", BackupType.FULL)
        backup = manager.create_backup(schedule.id, BackupType.FULL)
        manager.start_backup(backup.id)
        result = manager.complete_backup(backup.id, size_bytes=1024000, checksum="abc123")
        assert result is True
        assert backup.status == BackupStatus.COMPLETED
        assert backup.size_bytes == 1024000
        assert backup.checksum == "abc123"

    def test_fail_backup(self):
        """Test failing a backup"""
        manager = BackupManager()
        schedule = manager.create_schedule("daily", BackupType.FULL)
        backup = manager.create_backup(schedule.id, BackupType.FULL)
        manager.start_backup(backup.id)
        result = manager.fail_backup(backup.id)
        assert result is True
        assert backup.status == BackupStatus.FAILED

    def test_get_due_schedules(self):
        """Test getting schedules due for backup"""
        manager = BackupManager()
        schedule = manager.create_schedule("daily", BackupType.FULL, interval_hours=24)
        due = manager.get_due_schedules()
        assert len(due) == 1
        assert due[0].id == schedule.id

    def test_get_expired_backups(self):
        """Test getting expired backups"""
        manager = BackupManager()
        schedule = manager.create_schedule("daily", BackupType.FULL, retention_days=0)
        backup = manager.create_backup(schedule.id, BackupType.FULL)
        manager.start_backup(backup.id)
        manager.complete_backup(backup.id, 1000)
        # Set expires_at to past
        backup.expires_at = datetime.utcnow() - timedelta(days=1)
        expired = manager.get_expired_backups()
        assert len(expired) == 1

    def test_enable_disable_schedule(self):
        """Test enabling and disabling schedules"""
        manager = BackupManager()
        schedule = manager.create_schedule("daily", BackupType.FULL)
        manager.disable_schedule(schedule.id)
        assert schedule.enabled is False
        manager.enable_schedule(schedule.id)
        assert schedule.enabled is True

    def test_metrics_tracking(self):
        """Test metrics tracking"""
        manager = BackupManager()
        schedule = manager.create_schedule("daily", BackupType.FULL)
        backup = manager.create_backup(schedule.id, BackupType.FULL)
        manager.start_backup(backup.id)
        manager.complete_backup(backup.id, 5000)

        metrics = manager.get_metrics()
        assert metrics["total_backups"] == 1
        assert metrics["successful"] == 1
        assert metrics["total_size_bytes"] == 5000


# =============================================================================
# RESTORE MANAGER TESTS
# =============================================================================

class TestRestoreManager:
    """Tests for RestoreManager class"""

    def test_init(self):
        """Test manager initialization"""
        manager = RestoreManager()
        assert manager is not None
        metrics = manager.get_metrics()
        assert metrics["total_restores"] == 0

    def test_create_restore_point(self):
        """Test creating a restore point"""
        manager = RestoreManager()
        point = manager.create_restore_point(
            name="pre_restore",
            backup_id="backup_001",
            data_snapshot={"key": "value"}
        )
        assert point.name == "pre_restore"
        assert point.backup_id == "backup_001"
        assert point.data_snapshot["key"] == "value"

    def test_initiate_restore(self):
        """Test initiating a restore"""
        manager = RestoreManager()
        operation = manager.initiate_restore(
            backup_id="backup_001",
            target_location="production",
            validate_before_restore=True
        )
        assert operation.backup_id == "backup_001"
        assert operation.target_location == "production"
        assert operation.status == RestoreStatus.PENDING
        assert operation.validate_before_restore is True

    def test_start_restore(self):
        """Test starting a restore"""
        manager = RestoreManager()
        operation = manager.initiate_restore("backup_001", "production", validate_before_restore=True)
        result = manager.start_restore(operation.id)
        assert result is True
        assert operation.status == RestoreStatus.VALIDATING
        assert operation.pre_restore_snapshot_id is not None

    def test_start_restore_without_validation(self):
        """Test starting restore without validation"""
        manager = RestoreManager()
        operation = manager.initiate_restore("backup_001", "production", validate_before_restore=False)
        result = manager.start_restore(operation.id)
        assert result is True
        assert operation.status == RestoreStatus.IN_PROGRESS

    def test_validate_complete_success(self):
        """Test validation complete with success"""
        manager = RestoreManager()
        operation = manager.initiate_restore("backup_001", "production", validate_before_restore=True)
        manager.start_restore(operation.id)
        result = manager.validate_complete(operation.id, success=True)
        assert result is True
        assert operation.status == RestoreStatus.IN_PROGRESS

    def test_validate_complete_failure(self):
        """Test validation complete with failure"""
        manager = RestoreManager()
        operation = manager.initiate_restore("backup_001", "production", validate_before_restore=True)
        manager.start_restore(operation.id)
        result = manager.validate_complete(operation.id, success=False)
        assert result is True
        assert operation.status == RestoreStatus.FAILED

    def test_update_progress(self):
        """Test updating restore progress"""
        manager = RestoreManager()
        operation = manager.initiate_restore("backup_001", "production", validate_before_restore=False)
        manager.start_restore(operation.id)
        result = manager.update_progress(operation.id, items_restored=50, total_items=100)
        assert result is True
        assert operation.items_restored == 50
        assert operation.progress_percent == 50

    def test_complete_restore(self):
        """Test completing a restore"""
        manager = RestoreManager()
        operation = manager.initiate_restore("backup_001", "production", validate_before_restore=False)
        manager.start_restore(operation.id)
        manager.update_progress(operation.id, 100, 100)
        result = manager.complete_restore(operation.id)
        assert result is True
        assert operation.status == RestoreStatus.COMPLETED
        assert operation.progress_percent == 100

    def test_fail_restore(self):
        """Test failing a restore"""
        manager = RestoreManager()
        operation = manager.initiate_restore("backup_001", "production")
        result = manager.fail_restore(operation.id, "Connection lost")
        assert result is True
        assert operation.status == RestoreStatus.FAILED
        assert operation.error_message == "Connection lost"

    def test_rollback_restore(self):
        """Test rolling back a restore"""
        manager = RestoreManager()
        operation = manager.initiate_restore("backup_001", "production")
        manager.start_restore(operation.id)
        result = manager.rollback_restore(operation.id)
        assert result is True
        assert operation.status == RestoreStatus.ROLLED_BACK

    def test_cancel_operation(self):
        """Test cancelling a pending operation"""
        manager = RestoreManager()
        operation = manager.initiate_restore("backup_001", "production")
        result = manager.cancel_operation(operation.id)
        assert result is True
        assert operation.status == RestoreStatus.FAILED

    def test_get_active_operations(self):
        """Test getting active operations"""
        manager = RestoreManager()
        manager.initiate_restore("backup_001", "production")
        op2 = manager.initiate_restore("backup_002", "production")
        manager.start_restore(op2.id)

        active = manager.get_active_operations()
        assert len(active) == 2

    def test_metrics_tracking(self):
        """Test metrics tracking"""
        manager = RestoreManager()
        operation = manager.initiate_restore("backup_001", "production", validate_before_restore=False)
        manager.start_restore(operation.id)
        manager.complete_restore(operation.id)

        metrics = manager.get_metrics()
        assert metrics["total_restores"] == 1
        assert metrics["successful"] == 1


# =============================================================================
# FAILOVER MANAGER TESTS
# =============================================================================

class TestFailoverManager:
    """Tests for FailoverManager class"""

    def test_init(self):
        """Test manager initialization"""
        manager = FailoverManager()
        assert manager is not None
        metrics = manager.get_metrics()
        assert metrics["total_regions"] == 0

    def test_register_primary_region(self):
        """Test registering primary region"""
        manager = FailoverManager()
        region = manager.register_region(
            name="us-east-1",
            endpoint="https://us-east-1.example.com",
            priority=1,
            is_primary=True
        )
        assert region.name == "us-east-1"
        assert region.status == RegionStatus.PRIMARY
        assert manager.get_primary_region().id == region.id

    def test_register_standby_region(self):
        """Test registering standby region"""
        manager = FailoverManager()
        region = manager.register_region(
            name="eu-west-1",
            endpoint="https://eu-west-1.example.com",
            priority=2
        )
        assert region.status == RegionStatus.STANDBY

    def test_update_region_health(self):
        """Test updating region health"""
        manager = FailoverManager()
        region = manager.register_region("us-east-1", "https://us.example.com", is_primary=True)
        result = manager.update_region_health(region.id, is_healthy=False)
        assert result is True
        assert region.is_healthy is False

    def test_initiate_failover(self):
        """Test initiating failover"""
        manager = FailoverManager()
        primary = manager.register_region("us-east-1", "https://us.example.com", is_primary=True)
        standby = manager.register_region("eu-west-1", "https://eu.example.com", priority=2)

        event = manager.initiate_failover(
            from_region_id=primary.id,
            to_region_id=standby.id,
            reason="Maintenance"
        )
        assert event is not None
        assert event.status == FailoverStatus.FAILING_OVER
        assert event.reason == "Maintenance"

    def test_complete_failover(self):
        """Test completing failover"""
        manager = FailoverManager()
        primary = manager.register_region("us-east-1", "https://us.example.com", is_primary=True)
        standby = manager.register_region("eu-west-1", "https://eu.example.com", priority=2)

        event = manager.initiate_failover(primary.id, standby.id)
        manager.complete_dns_update(event.id)
        manager.complete_traffic_switch(event.id)
        result = manager.complete_failover(event.id)

        assert result is True
        assert event.status == FailoverStatus.FAILOVER_COMPLETE
        assert manager.get_primary_region().id == standby.id

    def test_fail_failover(self):
        """Test failing a failover"""
        manager = FailoverManager()
        primary = manager.register_region("us-east-1", "https://us.example.com", is_primary=True)
        standby = manager.register_region("eu-west-1", "https://eu.example.com", priority=2)

        event = manager.initiate_failover(primary.id, standby.id)
        result = manager.fail_failover(event.id, "DNS update failed")

        assert result is True
        assert event.status == FailoverStatus.FAILED

    def test_get_standby_regions(self):
        """Test getting standby regions"""
        manager = FailoverManager()
        manager.register_region("us-east-1", "https://us.example.com", is_primary=True)
        manager.register_region("eu-west-1", "https://eu.example.com", priority=2)
        manager.register_region("ap-south-1", "https://ap.example.com", priority=3)

        standbys = manager.get_standby_regions()
        assert len(standbys) == 2

    def test_get_healthy_regions(self):
        """Test getting healthy regions"""
        manager = FailoverManager()
        r1 = manager.register_region("us-east-1", "https://us.example.com", is_primary=True)
        r2 = manager.register_region("eu-west-1", "https://eu.example.com", priority=2)

        manager.update_region_health(r1.id, is_healthy=True)
        manager.update_region_health(r2.id, is_healthy=False)

        healthy = manager.get_healthy_regions()
        assert len(healthy) == 1

    def test_set_region_offline(self):
        """Test setting region offline"""
        manager = FailoverManager()
        region = manager.register_region("us-east-1", "https://us.example.com")
        result = manager.set_region_offline(region.id)
        assert result is True
        assert region.status == RegionStatus.OFFLINE

    def test_bring_region_online(self):
        """Test bringing region online"""
        manager = FailoverManager()
        region = manager.register_region("us-east-1", "https://us.example.com")
        manager.set_region_offline(region.id)
        result = manager.bring_region_online(region.id)
        assert result is True
        assert region.status == RegionStatus.STANDBY

    def test_get_failover_status(self):
        """Test getting failover status"""
        manager = FailoverManager()
        primary = manager.register_region("us-east-1", "https://us.example.com", is_primary=True)

        status = manager.get_failover_status()
        assert status == FailoverStatus.HEALTHY

        manager.update_region_health(primary.id, is_healthy=False)
        status = manager.get_failover_status()
        assert status == FailoverStatus.DEGRADED

    def test_metrics_tracking(self):
        """Test metrics tracking"""
        manager = FailoverManager()
        primary = manager.register_region("us-east-1", "https://us.example.com", is_primary=True)
        standby = manager.register_region("eu-west-1", "https://eu.example.com", priority=2)

        event = manager.initiate_failover(primary.id, standby.id)
        manager.complete_failover(event.id)

        metrics = manager.get_metrics()
        assert metrics["total_regions"] == 2
        assert metrics["total_failovers"] == 1
        assert metrics["successful"] == 1
