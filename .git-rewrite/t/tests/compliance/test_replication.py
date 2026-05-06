"""
Cross-Region Replication Tests.

Tests for replication service, monitoring, and latency tracking.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.compliance.replication.cross_region_replication import (
    CrossRegionReplication,
    ReplicationConfig,
    ReplicationStatus,
    ReplicationType,
    Region,
    get_cross_region_replication
)
from backend.compliance.replication.replication_monitor import (
    ReplicationMonitor,
    AlertConfig,
    HealthStatus,
    get_replication_monitor
)
from backend.compliance.replication.conflict_resolver import (
    ConflictResolver,
    ConflictType,
    ResolutionStrategy,
    ConflictStatus,
    get_conflict_resolver
)
from backend.compliance.replication.latency_tracker import (
    LatencyTracker,
    LatencyConfig,
    get_latency_tracker
)


class TestCrossRegionReplication:
    """Test cross-region replication service."""

    def test_replication_creation(self):
        """Test creating a replication service."""
        service = CrossRegionReplication()
        assert service is not None

    def test_queue_event(self):
        """Test queuing an event for replication."""
        service = CrossRegionReplication()

        event = service.queue_event(
            event_id="evt-001",
            source_region=Region.EU,
            target_region=Region.US,
            data_type="ticket",
            payload={"id": "T001", "subject": "Test"}
        )

        assert event.event_id == "evt-001"
        assert service.get_queue_size() == 1

    @pytest.mark.asyncio
    async def test_replicate_event(self):
        """Test replicating an event."""
        service = CrossRegionReplication()

        event = service.queue_event(
            event_id="evt-001",
            source_region=Region.EU,
            target_region=Region.US,
            data_type="ticket",
            payload={"id": "T001"}
        )

        result = await service.replicate_event(event)

        assert result.status == ReplicationStatus.COMPLETED
        assert result.lag_ms >= 0

    @pytest.mark.asyncio
    async def test_replicate_with_retry(self):
        """Test replication with retry."""
        service = CrossRegionReplication(config=ReplicationConfig(retry_attempts=3))

        event = service.queue_event(
            event_id="evt-001",
            source_region=Region.EU,
            target_region=Region.US,
            data_type="ticket",
            payload={"id": "T001"}
        )

        result = await service.replicate_with_retry(event)

        assert result.status in [ReplicationStatus.COMPLETED, ReplicationStatus.FAILED]
        assert result.attempts >= 1

    @pytest.mark.asyncio
    async def test_process_queue(self):
        """Test processing the queue."""
        service = CrossRegionReplication()

        # Queue multiple events
        for i in range(3):
            service.queue_event(
                event_id=f"evt-{i:03d}",
                source_region=Region.EU,
                target_region=Region.US,
                data_type="ticket",
                payload={"id": f"T{i}"}
            )

        results = await service.process_queue()

        assert len(results) == 3
        assert service.get_queue_size() == 0

    def test_lag_stats(self):
        """Test getting lag statistics."""
        service = CrossRegionReplication()

        stats = service.get_lag_stats()

        assert "avg_lag_ms" in stats
        assert "max_lag_ms" in stats
        assert "min_lag_ms" in stats

    def test_stats(self):
        """Test getting statistics."""
        service = CrossRegionReplication()

        stats = service.get_stats()

        assert "total_events" in stats
        assert "completed" in stats
        assert "failed" in stats


class TestReplicationMonitor:
    """Test replication monitor."""

    def test_monitor_creation(self):
        """Test creating a monitor."""
        monitor = ReplicationMonitor()
        assert monitor is not None

    def test_update_region_stats(self):
        """Test updating region stats."""
        monitor = ReplicationMonitor()

        health = monitor.update_region_stats(
            region=Region.EU,
            lag_ms=100,
            queue_depth=50,
            error_rate=0.01
        )

        assert health.status == HealthStatus.HEALTHY
        assert health.lag_ms == 100

    def test_high_lag_detection(self):
        """Test detection of high lag."""
        monitor = ReplicationMonitor(
            alert_config=AlertConfig(lag_threshold_ms=500)
        )

        health = monitor.update_region_stats(
            region=Region.EU,
            lag_ms=600,  # Above threshold
            queue_depth=50,
            error_rate=0.01
        )

        assert health.status == HealthStatus.DEGRADED

        alerts = monitor.get_alerts()
        assert len(alerts) > 0
        assert alerts[0].alert_type == "high_lag"

    def test_high_error_rate_detection(self):
        """Test detection of high error rate."""
        monitor = ReplicationMonitor(
            alert_config=AlertConfig(error_rate_threshold=0.05)
        )

        health = monitor.update_region_stats(
            region=Region.US,
            lag_ms=100,
            queue_depth=50,
            error_rate=0.10  # 10% error rate
        )

        assert health.status == HealthStatus.UNHEALTHY

    def test_get_overall_status(self):
        """Test getting overall status."""
        monitor = ReplicationMonitor()

        # All healthy
        monitor.update_region_stats(Region.EU, 100, 50, 0.01)
        monitor.update_region_stats(Region.US, 100, 50, 0.01)

        status = monitor.get_overall_status()
        assert status == HealthStatus.HEALTHY

    def test_acknowledge_alert(self):
        """Test acknowledging an alert."""
        monitor = ReplicationMonitor(
            alert_config=AlertConfig(lag_threshold_ms=500)
        )

        monitor.update_region_stats(Region.EU, 600, 50, 0.01)

        alerts = monitor.get_alerts()
        assert len(alerts) > 0

        result = monitor.acknowledge_alert(alerts[0].alert_id)
        assert result is True

        unacknowledged = [a for a in monitor.get_alerts() if not a.acknowledged]
        assert len(unacknowledged) == 0

    def test_detect_lag_anomaly(self):
        """Test lag anomaly detection."""
        monitor = ReplicationMonitor()

        monitor.update_region_stats(Region.EU, 600, 50, 0.01)

        is_anomaly = monitor.detect_lag_anomaly(Region.EU, threshold_ms=500)
        assert is_anomaly is True

        is_anomaly = monitor.detect_lag_anomaly(Region.EU, threshold_ms=700)
        assert is_anomaly is False

    def test_dashboard_data(self):
        """Test getting dashboard data."""
        monitor = ReplicationMonitor()

        data = monitor.get_dashboard_data()

        assert "overall_status" in data
        assert "regions" in data
        assert "active_alerts" in data


class TestConflictResolver:
    """Test conflict resolver."""

    def test_resolver_creation(self):
        """Test creating a resolver."""
        resolver = ConflictResolver()
        assert resolver is not None

    def test_detect_conflict(self):
        """Test detecting a conflict."""
        resolver = ConflictResolver()

        conflict = resolver.detect_conflict(
            resource_id="res-001",
            source_region=Region.EU,
            target_region=Region.US,
            source_data={"id": "res-001", "value": "a"},
            target_data={"id": "res-001", "value": "b"},
            source_timestamp=datetime.now(),
            target_timestamp=datetime.now() - timedelta(minutes=1)
        )

        assert conflict is not None
        assert conflict.conflict_type == ConflictType.WRITE_WRITE

    def test_no_conflict_identical_data(self):
        """Test no conflict when data is identical."""
        resolver = ConflictResolver()

        conflict = resolver.detect_conflict(
            resource_id="res-001",
            source_region=Region.EU,
            target_region=Region.US,
            source_data={"id": "res-001", "value": "a"},
            target_data={"id": "res-001", "value": "a"},
            source_timestamp=datetime.now(),
            target_timestamp=datetime.now()
        )

        assert conflict is None

    def test_resolve_last_write_wins(self):
        """Test last-write-wins resolution."""
        resolver = ConflictResolver(default_strategy=ResolutionStrategy.LAST_WRITE_WINS)

        conflict = resolver.detect_conflict(
            resource_id="res-001",
            source_region=Region.EU,
            target_region=Region.US,
            source_data={"id": "res-001", "value": "newer"},
            target_data={"id": "res-001", "value": "older"},
            source_timestamp=datetime.now(),
            target_timestamp=datetime.now() - timedelta(minutes=1)
        )

        result = resolver.resolve(conflict)

        assert result.strategy == ResolutionStrategy.LAST_WRITE_WINS
        assert result.winner_region == Region.EU  # Source is newer

    def test_resolve_first_write_wins(self):
        """Test first-write-wins resolution."""
        resolver = ConflictResolver(default_strategy=ResolutionStrategy.FIRST_WRITE_WINS)

        conflict = resolver.detect_conflict(
            resource_id="res-001",
            source_region=Region.EU,
            target_region=Region.US,
            source_data={"id": "res-001", "value": "newer"},
            target_data={"id": "res-001", "value": "older"},
            source_timestamp=datetime.now(),
            target_timestamp=datetime.now() - timedelta(minutes=1)
        )

        result = resolver.resolve(conflict)

        assert result.strategy == ResolutionStrategy.FIRST_WRITE_WINS
        assert result.winner_region == Region.US  # Target is older (first)

    def test_manual_resolve(self):
        """Test manual resolution."""
        resolver = ConflictResolver(default_strategy=ResolutionStrategy.MANUAL)

        conflict = resolver.detect_conflict(
            resource_id="res-001",
            source_region=Region.EU,
            target_region=Region.US,
            source_data={"id": "res-001", "value": "a"},
            target_data={"id": "res-001", "value": "b"},
            source_timestamp=datetime.now(),
            target_timestamp=datetime.now()
        )

        # Manual resolution
        result = resolver.manual_resolve(
            conflict_id=conflict.conflict_id,
            winner_region=Region.APAC,
            winning_data={"id": "res-001", "value": "manual"},
            resolved_by="admin@example.com"
        )

        assert result.strategy == ResolutionStrategy.MANUAL
        assert result.winner_region == Region.APAC

    def test_get_pending_conflicts(self):
        """Test getting pending conflicts."""
        resolver = ConflictResolver(default_strategy=ResolutionStrategy.MANUAL)

        conflict = resolver.detect_conflict(
            resource_id="res-001",
            source_region=Region.EU,
            target_region=Region.US,
            source_data={"value": "a"},
            target_data={"value": "b"},
            source_timestamp=datetime.now(),
            target_timestamp=datetime.now()
        )

        # Try to resolve with MANUAL strategy - should set status to PENDING_MANUAL
        try:
            resolver.resolve(conflict)
        except ValueError:
            # Expected - manual resolution required
            pass

        pending = resolver.get_pending_conflicts()
        assert len(pending) == 1

    def test_stats(self):
        """Test getting statistics."""
        resolver = ConflictResolver()

        stats = resolver.get_stats()

        assert "total_conflicts" in stats
        assert "resolved" in stats
        assert "pending_manual" in stats


class TestLatencyTracker:
    """Test latency tracker."""

    def test_tracker_creation(self):
        """Test creating a tracker."""
        tracker = LatencyTracker()
        assert tracker is not None

    def test_record_latency(self):
        """Test recording latency."""
        tracker = LatencyTracker()

        sample = tracker.record(
            source_region=Region.EU,
            target_region=Region.US,
            latency_ms=150,
            operation="replication"
        )

        assert sample.latency_ms == 150
        assert sample.success is True

    def test_latency_alert(self):
        """Test latency alert generation."""
        tracker = LatencyTracker(config=LatencyConfig(alert_threshold_ms=500))

        tracker.record(
            source_region=Region.EU,
            target_region=Region.US,
            latency_ms=600  # Above threshold
        )

        alerts = tracker.get_alerts()
        assert len(alerts) == 1
        assert alerts[0].latency_ms == 600

    def test_get_metrics(self):
        """Test getting latency metrics."""
        tracker = LatencyTracker()

        # Record multiple samples
        for latency in [100, 150, 200, 250, 300]:
            tracker.record(
                source_region=Region.EU,
                target_region=Region.US,
                latency_ms=latency
            )

        metrics = tracker.get_metrics(Region.EU, Region.US)

        assert metrics is not None
        assert metrics.sample_count == 5
        assert metrics.min_ms == 100
        assert metrics.max_ms == 300

    def test_percentiles(self):
        """Test percentile calculations."""
        tracker = LatencyTracker()

        # Record many samples for accurate percentiles
        for i in range(100):
            tracker.record(
                source_region=Region.EU,
                target_region=Region.US,
                latency_ms=i + 1  # 1-100
            )

        metrics = tracker.get_metrics(Region.EU, Region.US)

        # P50 should be around 50
        assert 40 <= metrics.p50_ms <= 60
        # P95 should be around 95
        assert 85 <= metrics.p95_ms <= 100
        # P99 should be around 99
        assert 90 <= metrics.p99_ms <= 100

    def test_prometheus_export(self):
        """Test Prometheus export format."""
        tracker = LatencyTracker()

        tracker.record(Region.EU, Region.US, 150)
        tracker.record(Region.US, Region.APAC, 200)

        export = tracker.export_prometheus()

        assert "replication_latency_p50_ms" in export
        assert "replication_latency_p95_ms" in export
        assert "replication_latency_p99_ms" in export
        assert "replication_latency_alerts_total" in export

    def test_stats(self):
        """Test getting statistics."""
        tracker = LatencyTracker()

        tracker.record(Region.EU, Region.US, 150)
        tracker.record(Region.US, Region.APAC, 200, success=False)

        stats = tracker.get_stats()

        assert stats["total_samples"] == 2
        assert stats["successful_samples"] == 1
        assert stats["failed_samples"] == 1


class TestReplicationLagUnder500ms:
    """Test that replication lag stays under 500ms (CRITICAL)."""

    @pytest.mark.asyncio
    async def test_replication_lag_under_threshold(self):
        """Test that replication lag is under 500ms."""
        service = CrossRegionReplication(config=ReplicationConfig(max_lag_ms=500))

        # Run multiple replications
        for i in range(10):
            event = service.queue_event(
                event_id=f"evt-{i:03d}",
                source_region=Region.EU,
                target_region=Region.US,
                data_type="ticket",
                payload={"id": f"T{i}"}
            )
            await service.replicate_event(event)

        lag_stats = service.get_lag_stats()

        # Average lag should be reasonable (simulated is 10-100ms)
        assert lag_stats["avg_lag_ms"] < 500, "Average lag should be under 500ms"

    def test_lag_monitoring_threshold(self):
        """Test that monitor detects lag above 500ms."""
        monitor = ReplicationMonitor(
            alert_config=AlertConfig(lag_threshold_ms=500)
        )

        # Below threshold - should be healthy
        health = monitor.update_region_stats(
            region=Region.EU,
            lag_ms=450,
            queue_depth=50,
            error_rate=0.01
        )
        assert health.status == HealthStatus.HEALTHY

        # Above threshold - should be degraded
        health = monitor.update_region_stats(
            region=Region.EU,
            lag_ms=550,
            queue_depth=50,
            error_rate=0.01
        )
        assert health.status == HealthStatus.DEGRADED


class TestReplicationModuleStructure:
    """Test replication module structure."""

    def test_module_exists(self):
        """Test that replication module exists."""
        from backend.compliance.replication import (
            CrossRegionReplication,
            ReplicationMonitor,
            ConflictResolver,
            LatencyTracker
        )
        assert CrossRegionReplication is not None
        assert ReplicationMonitor is not None
        assert ConflictResolver is not None
        assert LatencyTracker is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
