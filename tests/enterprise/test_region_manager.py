# Tests for Builder 4 - Region Manager
# Week 51: region_manager.py, region_replicator.py, region_sync.py

import pytest
from datetime import datetime, timedelta
import time

from enterprise.global_infra.region_manager import (
    RegionManager, Region, RegionStatus, RegionTier
)
from enterprise.global_infra.region_replicator import (
    RegionReplicator, ReplicationJob, ReplicationLag, ReplicationMode, ReplicationStatus
)
from enterprise.global_infra.region_sync import (
    RegionSync, SyncItem, SyncSession, SyncConflict, SyncStatus
)


# =============================================================================
# REGION MANAGER TESTS
# =============================================================================

class TestRegionManager:
    """Tests for RegionManager class"""

    def test_init(self):
        """Test manager initialization"""
        manager = RegionManager()
        assert manager is not None
        metrics = manager.get_metrics()
        assert metrics["total_regions"] == 0

    def test_create_region(self):
        """Test creating a region"""
        manager = RegionManager()
        region = manager.create_region(
            name="US East",
            code="us-east-1",
            tier=RegionTier.PRIMARY,
            endpoint="https://us-east-1.example.com"
        )
        assert region.name == "US East"
        assert region.code == "us-east-1"
        assert region.status == RegionStatus.ACTIVE

    def test_update_region_status(self):
        """Test updating region status"""
        manager = RegionManager()
        region = manager.create_region("US East", "us-east-1")
        result = manager.update_region_status(region.id, RegionStatus.MAINTENANCE)
        assert result is True
        assert region.status == RegionStatus.MAINTENANCE

    def test_update_region_load(self):
        """Test updating region load"""
        manager = RegionManager()
        region = manager.create_region("US East", "us-east-1", capacity=100)
        result = manager.update_region_load(region.id, 50)
        assert result is True
        assert region.current_load == 50

    def test_get_region_by_code(self):
        """Test getting region by code"""
        manager = RegionManager()
        manager.create_region("US East", "us-east-1")
        region = manager.get_region_by_code("us-east-1")
        assert region is not None
        assert region.code == "us-east-1"

    def test_get_regions_by_tier(self):
        """Test getting regions by tier"""
        manager = RegionManager()
        manager.create_region("Primary", "us-east-1", tier=RegionTier.PRIMARY)
        manager.create_region("Secondary", "eu-west-1", tier=RegionTier.SECONDARY)
        manager.create_region("Edge", "ap-south-1", tier=RegionTier.EDGE)

        primary = manager.get_regions_by_tier(RegionTier.PRIMARY)
        assert len(primary) == 1

    def test_get_active_regions(self):
        """Test getting active regions"""
        manager = RegionManager()
        manager.create_region("US East", "us-east-1")
        manager.create_region("EU West", "eu-west-1")
        r3 = manager.create_region("APAC", "ap-south-1")
        manager.update_region_status(r3.id, RegionStatus.OFFLINE)

        active = manager.get_active_regions()
        assert len(active) == 2

    def test_get_available_regions(self):
        """Test getting available regions"""
        manager = RegionManager()
        manager.create_region("US East", "us-east-1", capacity=100)
        manager.create_region("EU West", "eu-west-1", capacity=50)

        available = manager.get_available_regions(min_capacity=75)
        assert len(available) == 1

    def test_get_region_with_least_load(self):
        """Test getting region with least load"""
        manager = RegionManager()
        r1 = manager.create_region("US East", "us-east-1", capacity=100)
        r2 = manager.create_region("EU West", "eu-west-1", capacity=100)
        manager.update_region_load(r1.id, 80)
        manager.update_region_load(r2.id, 20)

        least_loaded = manager.get_region_with_least_load()
        assert least_loaded.id == r2.id

    def test_check_compliance(self):
        """Test compliance checking"""
        manager = RegionManager()
        region = manager.create_region(
            "US East", "us-east-1",
            compliance_tags=["hipaa", "gdpr", "soc2"]
        )

        result = manager.check_compliance(region.id, ["hipaa", "gdpr"])
        assert result is True

        result = manager.check_compliance(region.id, ["pci-dss"])
        assert result is False

    def test_delete_region(self):
        """Test deleting a region"""
        manager = RegionManager()
        region = manager.create_region("US East", "us-east-1")
        result = manager.delete_region(region.id)
        assert result is True
        assert manager.get_region(region.id) is None

    def test_get_region_utilization(self):
        """Test getting region utilization"""
        manager = RegionManager()
        region = manager.create_region("US East", "us-east-1", capacity=100)
        manager.update_region_load(region.id, 75)

        utilization = manager.get_region_utilization(region.id)
        assert utilization == 75.0

    def test_get_metrics(self):
        """Test getting metrics"""
        manager = RegionManager()
        manager.create_region("US East", "us-east-1")
        manager.create_region("EU West", "eu-west-1")

        metrics = manager.get_metrics()
        assert metrics["total_regions"] == 2
        assert metrics["active_regions"] == 2


# =============================================================================
# REGION REPLICATOR TESTS
# =============================================================================

class TestRegionReplicator:
    """Tests for RegionReplicator class"""

    def test_init(self):
        """Test replicator initialization"""
        replicator = RegionReplicator()
        assert replicator is not None
        metrics = replicator.get_metrics()
        assert metrics["total_jobs"] == 0

    def test_configure_replication(self):
        """Test configuring replication"""
        replicator = RegionReplicator()
        replicator.configure_replication("us-east-1", "eu-west-1", ReplicationMode.ASYNC)

        mode = replicator.get_replication_config("us-east-1", "eu-west-1")
        assert mode == ReplicationMode.ASYNC

    def test_create_job(self):
        """Test creating a replication job"""
        replicator = RegionReplicator()
        job = replicator.create_job(
            source_region="us-east-1",
            target_regions=["eu-west-1", "ap-south-1"],
            data_type="user_data",
            data_id="user-123"
        )
        assert job.source_region == "us-east-1"
        assert len(job.target_regions) == 2
        assert job.status == ReplicationStatus.PENDING

    def test_start_job(self):
        """Test starting a job"""
        replicator = RegionReplicator()
        job = replicator.create_job("us-east-1", ["eu-west-1"], "data", "1")
        result = replicator.start_job(job.id)
        assert result is True
        assert job.status == ReplicationStatus.IN_PROGRESS

    def test_update_progress(self):
        """Test updating job progress"""
        replicator = RegionReplicator()
        job = replicator.create_job("us-east-1", ["eu-west-1"], "data", "1")
        replicator.start_job(job.id)
        result = replicator.update_progress(job.id, 50, 1024000)
        assert result is True
        assert job.progress == 50
        assert job.bytes_replicated == 1024000

    def test_complete_job(self):
        """Test completing a job"""
        replicator = RegionReplicator()
        replicator.configure_replication("us-east-1", "eu-west-1")
        job = replicator.create_job("us-east-1", ["eu-west-1"], "data", "1")
        replicator.start_job(job.id)
        replicator.update_progress(job.id, 100, 1024000)
        result = replicator.complete_job(job.id)
        assert result is True
        assert job.status == ReplicationStatus.COMPLETED

    def test_fail_job(self):
        """Test failing a job"""
        replicator = RegionReplicator()
        job = replicator.create_job("us-east-1", ["eu-west-1"], "data", "1")
        result = replicator.fail_job(job.id, "Connection refused")
        assert result is True
        assert job.status == ReplicationStatus.FAILED

    def test_update_lag(self):
        """Test updating replication lag"""
        replicator = RegionReplicator()
        replicator.configure_replication("us-east-1", "eu-west-1")
        result = replicator.update_lag("us-east-1", "eu-west-1", 150, 5)
        assert result is True

        lag = replicator.get_lag("us-east-1", "eu-west-1")
        assert lag.lag_ms == 150

    def test_get_active_jobs(self):
        """Test getting active jobs"""
        replicator = RegionReplicator()
        j1 = replicator.create_job("us-east-1", ["eu-west-1"], "data", "1")
        replicator.create_job("us-east-1", ["ap-south-1"], "data", "2")
        replicator.start_job(j1.id)

        active = replicator.get_active_jobs()
        assert len(active) == 1

    def test_get_metrics(self):
        """Test getting metrics"""
        replicator = RegionReplicator()
        replicator.configure_replication("us-east-1", "eu-west-1")
        job = replicator.create_job("us-east-1", ["eu-west-1"], "data", "1")
        replicator.start_job(job.id)
        replicator.update_progress(job.id, 100, 1024)
        replicator.complete_job(job.id)

        metrics = replicator.get_metrics()
        assert metrics["completed"] == 1
        assert metrics["bytes_replicated"] == 1024


# =============================================================================
# REGION SYNC TESTS
# =============================================================================

class TestRegionSync:
    """Tests for RegionSync class"""

    def test_init(self):
        """Test sync initialization"""
        sync = RegionSync()
        assert sync is not None
        metrics = sync.get_metrics()
        assert metrics["total_sessions"] == 0

    def test_set_and_get_item(self):
        """Test setting and getting items"""
        sync = RegionSync()
        sync.set_item("user:123", {"name": "John"}, "us-east-1")
        item = sync.get_item("user:123", "us-east-1")
        assert item is not None
        assert item.value["name"] == "John"

    def test_start_sync_session(self):
        """Test starting a sync session"""
        sync = RegionSync()
        session = sync.start_sync_session("us-east-1", "eu-west-1")
        assert session.source_region == "us-east-1"
        assert session.status == SyncStatus.SYNCING

    def test_sync_item_no_conflict(self):
        """Test syncing item without conflict"""
        sync = RegionSync()
        session = sync.start_sync_session("us-east-1", "eu-west-1")
        result = sync.sync_item(session.id, "key1", "value1", None)
        assert result is True
        assert session.items_synced == 1

    def test_sync_item_with_conflict(self):
        """Test syncing item with conflict"""
        sync = RegionSync()
        session = sync.start_sync_session("us-east-1", "eu-west-1")
        result = sync.sync_item(session.id, "key1", "value1", "different_value")
        assert result is False
        assert session.conflicts == 1

    def test_complete_session(self):
        """Test completing a session"""
        sync = RegionSync()
        session = sync.start_sync_session("us-east-1", "eu-west-1")
        sync.sync_item(session.id, "key1", "value1", None)
        result = sync.complete_session(session.id)
        assert result is True
        assert session.status == SyncStatus.IN_SYNC

    def test_complete_session_with_conflicts(self):
        """Test completing session with conflicts"""
        sync = RegionSync()
        session = sync.start_sync_session("us-east-1", "eu-west-1")
        sync.sync_item(session.id, "key1", "value1", "different")
        sync.complete_session(session.id)
        assert session.status == SyncStatus.CONFLICT

    def test_resolve_conflict(self):
        """Test resolving a conflict"""
        sync = RegionSync()
        session = sync.start_sync_session("us-east-1", "eu-west-1")
        sync.sync_item(session.id, "key1", "value1", "different")

        conflicts = sync.get_unresolved_conflicts()
        conflict_id = conflicts[0].id

        result = sync.resolve_conflict(conflict_id, "source_wins", "value1")
        assert result is True

    def test_get_active_sessions(self):
        """Test getting active sessions"""
        sync = RegionSync()
        sync.start_sync_session("us-east-1", "eu-west-1")
        sync.start_sync_session("us-east-1", "ap-south-1")

        active = sync.get_active_sessions()
        assert len(active) == 2

    def test_get_region_status(self):
        """Test getting region status"""
        sync = RegionSync()
        session = sync.start_sync_session("us-east-1", "eu-west-1")
        sync.sync_item(session.id, "key1", "value1", None)
        sync.complete_session(session.id)

        status = sync.get_region_status("us-east-1", "eu-west-1")
        assert status == SyncStatus.IN_SYNC

    def test_get_last_sync_time(self):
        """Test getting last sync time"""
        sync = RegionSync()
        session = sync.start_sync_session("us-east-1", "eu-west-1")
        sync.sync_item(session.id, "key1", "value1", None)
        sync.complete_session(session.id)

        last_sync = sync.get_last_sync_time("us-east-1", "eu-west-1")
        assert last_sync is not None

    def test_get_stale_regions(self):
        """Test getting stale regions"""
        sync = RegionSync()
        session = sync.start_sync_session("us-east-1", "eu-west-1")
        sync.sync_item(session.id, "key1", "value1", None)
        sync.complete_session(session.id)

        # With 0 minute max age, should find stale regions
        stale = sync.get_stale_regions(max_age_minutes=0)
        assert len(stale) >= 1

    def test_get_metrics(self):
        """Test getting metrics"""
        sync = RegionSync()
        session = sync.start_sync_session("us-east-1", "eu-west-1")
        sync.sync_item(session.id, "key1", "value1", None)
        sync.complete_session(session.id)

        metrics = sync.get_metrics()
        assert metrics["items_synced"] == 1
