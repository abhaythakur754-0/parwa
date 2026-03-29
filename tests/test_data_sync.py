"""
Week 58 - Builder 4 Tests: Data Sync Module
Unit tests for Sync Engine, Sync Scheduler, and Sync Monitor
"""

import pytest
import time
from parwa_integration_hub.sync_engine import (
    SyncEngine, SyncConfig, SyncRecord, SyncDirection, SyncStatus,
    ConflictStrategy, SyncResult, SyncScheduler, SyncMonitor
)


class TestSyncEngine:
    """Tests for SyncEngine class"""

    @pytest.fixture
    def engine(self):
        """Create test sync engine"""
        return SyncEngine()

    @pytest.fixture
    def sync_config(self):
        """Create test sync config"""
        return SyncConfig(
            name="test-sync",
            source="system-a",
            target="system-b",
            direction=SyncDirection.BIDIRECTIONAL,
            conflict_strategy=ConflictStrategy.LATEST_WINS
        )

    @pytest.fixture
    def sync_record(self):
        """Create test sync record"""
        return SyncRecord(
            id="record-1",
            source_id="src-1",
            target_id="tgt-1",
            entity_type="user",
            source_data={"name": "Alice", "email": "alice@example.com"},
            target_data={"name": "Alice", "email": "alice@example.com"},
            source_timestamp=time.time(),
            target_timestamp=time.time(),
            checksum="abc123"
        )

    def test_register_sync(self, engine, sync_config):
        """Test sync registration"""
        engine.register_sync(sync_config)

        assert "test-sync" in engine.configs
        assert engine.status["test-sync"] == SyncStatus.PENDING

    def test_unregister_sync(self, engine, sync_config):
        """Test sync unregistration"""
        engine.register_sync(sync_config)
        result = engine.unregister_sync("test-sync")

        assert result is True
        assert "test-sync" not in engine.configs

    def test_unregister_nonexistent_sync(self, engine):
        """Test unregistering nonexistent sync"""
        result = engine.unregister_sync("nonexistent")
        assert result is False

    def test_sync_single_record(self, engine, sync_config, sync_record):
        """Test syncing single record"""
        engine.register_sync(sync_config)

        result = engine.sync_record("test-sync", sync_record)

        assert result.status == SyncStatus.COMPLETED
        assert result.records_processed == 1

    def test_sync_batch(self, engine, sync_config):
        """Test syncing batch of records"""
        engine.register_sync(sync_config)

        records = [
            SyncRecord(
                id=f"record-{i}",
                source_id=f"src-{i}",
                target_id=f"tgt-{i}",
                entity_type="user",
                source_data={"name": f"User {i}"},
                target_data={"name": f"User {i}"},
                source_timestamp=time.time(),
                target_timestamp=time.time(),
                checksum=f"checksum-{i}"
            )
            for i in range(5)
        ]

        result = engine.sync_batch("test-sync", records)

        assert result.status == SyncStatus.COMPLETED
        assert result.records_processed == 5

    def test_conflict_detection(self, engine, sync_config):
        """Test conflict detection"""
        engine.register_sync(sync_config)

        record = SyncRecord(
            id="conflict-record",
            source_id="src-1",
            target_id="tgt-1",
            entity_type="user",
            source_data={"name": "Alice"},
            target_data={"name": "Bob"},
            source_timestamp=time.time() + 100,
            target_timestamp=time.time(),
            checksum="different"
        )

        result = engine.sync_record("test-sync", record)

        assert result.conflicts == 1

    def test_conflict_resolution_source_wins(self, engine):
        """Test source wins conflict resolution"""
        config = SyncConfig(
            name="source-wins-sync",
            source="a",
            target="b",
            conflict_strategy=ConflictStrategy.SOURCE_WINS
        )
        engine.register_sync(config)

        record = SyncRecord(
            id="conflict",
            source_id="s1",
            target_id="t1",
            entity_type="user",
            source_data={"name": "Source"},
            target_data={"name": "Target"},
            source_timestamp=time.time(),
            target_timestamp=time.time() + 100,
            checksum="diff"
        )

        result = engine.sync_record("source-wins-sync", record)
        assert result.status == SyncStatus.COMPLETED

    def test_conflict_resolution_target_wins(self, engine):
        """Test target wins conflict resolution"""
        config = SyncConfig(
            name="target-wins-sync",
            source="a",
            target="b",
            conflict_strategy=ConflictStrategy.TARGET_WINS
        )
        engine.register_sync(config)

        record = SyncRecord(
            id="conflict",
            source_id="s1",
            target_id="t1",
            entity_type="user",
            source_data={"name": "Source"},
            target_data={"name": "Target"},
            source_timestamp=time.time(),
            target_timestamp=time.time(),
            checksum="diff"
        )

        result = engine.sync_record("target-wins-sync", record)
        assert result.status == SyncStatus.COMPLETED

    def test_get_sync_status(self, engine, sync_config):
        """Test get sync status"""
        engine.register_sync(sync_config)

        status = engine.get_sync_status("test-sync")
        assert status == SyncStatus.PENDING

    def test_get_result(self, engine, sync_config, sync_record):
        """Test get sync result"""
        engine.register_sync(sync_config)
        result = engine.sync_record("test-sync", sync_record)

        retrieved = engine.get_result(result.sync_id)
        assert retrieved is not None
        assert retrieved.status == SyncStatus.COMPLETED

    def test_get_stats(self, engine, sync_config, sync_record):
        """Test get sync statistics"""
        engine.register_sync(sync_config)
        engine.sync_record("test-sync", sync_record)

        stats = engine.get_stats()
        assert "test-sync" in stats
        assert stats["test-sync"]["records"] == 1


class TestSyncScheduler:
    """Tests for SyncScheduler class"""

    @pytest.fixture
    def scheduler(self):
        """Create test scheduler"""
        engine = SyncEngine()
        return SyncScheduler(engine)

    @pytest.fixture
    def setup_sync(self, scheduler):
        """Setup sync configuration"""
        config = SyncConfig(
            name="scheduled-sync",
            source="a",
            target="b"
        )
        scheduler.engine.register_sync(config)
        return config

    def test_schedule_sync(self, scheduler, setup_sync):
        """Test scheduling sync"""
        scheduler.schedule_sync("scheduled-sync", interval=60)

        assert "scheduled-sync" in scheduler.schedules

    def test_unschedule_sync(self, scheduler, setup_sync):
        """Test unscheduling sync"""
        scheduler.schedule_sync("scheduled-sync", 60)
        result = scheduler.unschedule_sync("scheduled-sync")

        assert result is True
        assert "scheduled-sync" not in scheduler.schedules

    def test_run_sync(self, scheduler, setup_sync):
        """Test running scheduled sync"""
        scheduler.schedule_sync("scheduled-sync", 60)

        result = scheduler.run_sync("scheduled-sync")

        assert result is not None
        assert result.status == SyncStatus.COMPLETED

    def test_get_next_run(self, scheduler, setup_sync):
        """Test get next run time"""
        scheduler.schedule_sync("scheduled-sync", 60)

        next_run = scheduler.get_next_run("scheduled-sync")

        assert next_run is not None
        assert next_run > time.time()

    def test_get_schedule(self, scheduler, setup_sync):
        """Test get schedule info"""
        scheduler.schedule_sync("scheduled-sync", 60)

        schedule = scheduler.get_schedule("scheduled-sync")

        assert schedule is not None
        assert schedule["interval"] == 60

    def test_list_schedules(self, scheduler, setup_sync):
        """Test list all schedules"""
        scheduler.schedule_sync("scheduled-sync", 60)

        schedules = scheduler.list_schedules()

        assert "scheduled-sync" in schedules


class TestSyncMonitor:
    """Tests for SyncMonitor class"""

    @pytest.fixture
    def monitor(self):
        """Create test monitor"""
        engine = SyncEngine()
        scheduler = SyncScheduler(engine)
        return SyncMonitor(engine, scheduler)

    @pytest.fixture
    def setup_sync(self, monitor):
        """Setup sync configuration"""
        config = SyncConfig(name="monitored-sync", source="a", target="b")
        monitor.engine.register_sync(config)
        return config

    def test_get_sync_health(self, monitor, setup_sync):
        """Test get sync health"""
        health = monitor.get_sync_health("monitored-sync")

        assert health["name"] == "monitored-sync"
        assert "status" in health

    def test_get_all_health(self, monitor, setup_sync):
        """Test get all syncs health"""
        health = monitor.get_all_health()

        assert "monitored-sync" in health

    def test_record_alert(self, monitor, setup_sync):
        """Test recording alert"""
        monitor.record_alert("monitored-sync", "Test alert", "warning")

        alerts = monitor.get_alerts()
        assert len(alerts) == 1
        assert alerts[0]["message"] == "Test alert"

    def test_get_alerts_filtered(self, monitor, setup_sync):
        """Test get filtered alerts"""
        monitor.record_alert("monitored-sync", "Alert 1")
        monitor.record_alert("other-sync", "Alert 2")

        alerts = monitor.get_alerts(sync_name="monitored-sync")
        assert len(alerts) == 1

    def test_clear_alerts(self, monitor, setup_sync):
        """Test clearing alerts"""
        monitor.record_alert("monitored-sync", "Alert")
        count = monitor.clear_alerts()

        assert count == 1
        assert len(monitor.alerts) == 0

    def test_get_recovery_suggestions(self, monitor, setup_sync):
        """Test get recovery suggestions"""
        suggestions = monitor.get_recovery_suggestions("monitored-sync")

        assert isinstance(suggestions, list)

    def test_get_recovery_suggestions_for_failed(self, monitor, setup_sync):
        """Test recovery suggestions for failed sync"""
        monitor.engine.status["monitored-sync"] = SyncStatus.FAILED

        suggestions = monitor.get_recovery_suggestions("monitored-sync")

        assert len(suggestions) > 0
