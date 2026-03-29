"""
Integration tests for Undo Flow.

Tests the complete undo operation flow including:
- Snapshot creation flow
- Restoration flow
- Multi-level undo
- Concurrent operations
"""
import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from unittest.mock import Mock, AsyncMock, patch

from services.undo_manager import (
    UndoManager,
    UndoConfig,
    UndoSnapshot,
    UndoableActionType,
    UndoStatus,
    SnapshotStatus,
)


class TestUndoSnapshot:
    """Test UndoSnapshot functionality."""
    
    def test_snapshot_creation(self):
        """Test basic snapshot creation."""
        snapshot = UndoSnapshot(
            snapshot_id="snap_123",
            action_type=UndoableActionType.TICKET_STATUS_CHANGE,
            company_id="company_123",
            performed_by="user_456",
            created_at=datetime.now(timezone.utc),
            state_before={"status": "open"},
            state_after={"status": "resolved"},
            can_undo=True,
            undo_window_hours=24,
        )
        
        assert snapshot.snapshot_id == "snap_123"
        assert snapshot.action_type == UndoableActionType.TICKET_STATUS_CHANGE
        assert snapshot.can_undo is True
        assert snapshot.status == SnapshotStatus.ACTIVE
    
    def test_snapshot_expiration(self):
        """Test snapshot expiration check."""
        # Not expired snapshot
        snapshot = UndoSnapshot(
            snapshot_id="snap_123",
            action_type=UndoableActionType.TICKET_STATUS_CHANGE,
            company_id="company_123",
            performed_by="user_456",
            created_at=datetime.now(timezone.utc),
            state_before={},
            state_after={},
            can_undo=True,
            undo_window_hours=24,
        )
        
        assert snapshot.is_expired is False
        
        # Expired snapshot
        old_snapshot = UndoSnapshot(
            snapshot_id="snap_old",
            action_type=UndoableActionType.TICKET_STATUS_CHANGE,
            company_id="company_123",
            performed_by="user_456",
            created_at=datetime.now(timezone.utc) - timedelta(hours=25),
            state_before={},
            state_after={},
            can_undo=True,
            undo_window_hours=24,
        )
        
        assert old_snapshot.is_expired is True
    
    def test_snapshot_financial_detection(self):
        """Test financial action detection."""
        # Non-financial action
        snapshot = UndoSnapshot(
            snapshot_id="snap_123",
            action_type=UndoableActionType.TICKET_STATUS_CHANGE,
            company_id="company_123",
            performed_by="user_456",
            created_at=datetime.now(timezone.utc),
            state_before={},
            state_after={},
            can_undo=True,
            undo_window_hours=24,
        )
        
        assert snapshot.is_financial is False
        
        # Financial action
        financial_snapshot = UndoSnapshot(
            snapshot_id="snap_fin",
            action_type=UndoableActionType.REFUND,
            company_id="company_123",
            performed_by="user_456",
            created_at=datetime.now(timezone.utc),
            state_before={},
            state_after={},
            can_undo=False,
            undo_window_hours=24,
        )
        
        assert financial_snapshot.is_financial is True


class TestSnapshotCreationFlow:
    """Test snapshot creation flow."""
    
    @pytest.fixture
    def undo_manager(self):
        """Create an UndoManager instance."""
        return UndoManager(config=UndoConfig(max_undo_levels=10))
    
    @pytest.mark.asyncio
    async def test_create_snapshot_basic(self, undo_manager):
        """Test basic snapshot creation."""
        snapshot = await undo_manager.create_snapshot({
            "action_type": "ticket_status_change",
            "company_id": "company_123",
            "performed_by": "user_456",
            "state_before": {"status": "open"},
            "state_after": {"status": "resolved"},
        })
        
        assert snapshot.snapshot_id.startswith("snap_")
        assert snapshot.action_type == UndoableActionType.TICKET_STATUS_CHANGE
        assert snapshot.can_undo is True
        assert snapshot.status == SnapshotStatus.ACTIVE
    
    @pytest.mark.asyncio
    async def test_create_snapshot_for_financial_action(self, undo_manager):
        """Test snapshot creation for non-undoable financial action."""
        snapshot = await undo_manager.create_snapshot({
            "action_type": "refund",
            "company_id": "company_123",
            "performed_by": "user_456",
            "state_before": {"amount": 100.00},
            "state_after": {"refunded": True},
        })
        
        assert snapshot.can_undo is False
        assert snapshot.is_financial is True
    
    @pytest.mark.asyncio
    async def test_create_snapshot_with_group(self, undo_manager):
        """Test snapshot creation with group for atomic operations."""
        group_id = undo_manager.create_group(
            company_id="company_123",
            description="Multi-step ticket update"
        )
        
        snapshot = await undo_manager.create_snapshot({
            "action_type": "ticket_status_change",
            "company_id": "company_123",
            "performed_by": "user_456",
            "state_before": {"status": "open"},
            "state_after": {"status": "in_progress"},
            "group_id": group_id,
        })
        
        assert snapshot.group_id == group_id
    
    @pytest.mark.asyncio
    async def test_snapshot_added_to_undo_stack(self, undo_manager):
        """Test that snapshot is added to undo stack."""
        company_id = "company_123"
        
        await undo_manager.create_snapshot({
            "action_type": "ticket_status_change",
            "company_id": company_id,
            "performed_by": "user_456",
            "state_before": {"status": "open"},
            "state_after": {"status": "resolved"},
        })
        
        stack = undo_manager._undo_stack.get(company_id, [])
        assert len(stack) == 1
    
    @pytest.mark.asyncio
    async def test_undo_stack_respects_max_levels(self, undo_manager):
        """Test that undo stack respects max_undo_levels."""
        company_id = "company_123"
        
        # Create more snapshots than max levels
        for i in range(15):
            await undo_manager.create_snapshot({
                "action_type": "ticket_status_change",
                "company_id": company_id,
                "performed_by": "user_456",
                "state_before": {"status": f"status_{i}"},
                "state_after": {"status": f"status_{i+1}"},
            })
        
        stack = undo_manager._undo_stack.get(company_id, [])
        assert len(stack) == undo_manager.config.max_undo_levels


class TestRestorationFlow:
    """Test restoration flow."""
    
    @pytest.fixture
    def undo_manager(self):
        """Create an UndoManager instance."""
        return UndoManager(config=UndoConfig())
    
    @pytest.mark.asyncio
    async def test_undo_basic(self, undo_manager):
        """Test basic undo operation."""
        snapshot = await undo_manager.create_snapshot({
            "action_type": "ticket_status_change",
            "company_id": "company_123",
            "performed_by": "user_456",
            "state_before": {"status": "open", "ticket_id": "T-123"},
            "state_after": {"status": "resolved", "ticket_id": "T-123"},
        })
        
        result = await undo_manager.undo(snapshot.snapshot_id)
        
        assert result["success"] is True
        assert result["status"] == UndoStatus.COMPLETED.value
        assert result["restored_state"] == {"status": "open", "ticket_id": "T-123"}
    
    @pytest.mark.asyncio
    async def test_undo_financial_action_blocked(self, undo_manager):
        """Test that financial actions cannot be undone."""
        snapshot = await undo_manager.create_snapshot({
            "action_type": "refund",
            "company_id": "company_123",
            "performed_by": "user_456",
            "state_before": {"refunded": False},
            "state_after": {"refunded": True, "amount": 100.00},
        })
        
        result = await undo_manager.undo(snapshot.snapshot_id)
        
        assert result["success"] is False
        assert result["status"] == UndoStatus.NOT_UNDOABLE.value
        assert result["is_financial"] is True
    
    @pytest.mark.asyncio
    async def test_undo_nonexistent_snapshot(self, undo_manager):
        """Test undo with invalid snapshot ID."""
        result = await undo_manager.undo("nonexistent_id")
        
        assert result["success"] is False
        assert result["status"] == UndoStatus.FAILED.value
    
    @pytest.mark.asyncio
    async def test_undo_expired_snapshot(self, undo_manager):
        """Test undo of expired snapshot."""
        snapshot = UndoSnapshot(
            snapshot_id="snap_expired",
            action_type=UndoableActionType.TICKET_STATUS_CHANGE,
            company_id="company_123",
            performed_by="user_456",
            created_at=datetime.now(timezone.utc) - timedelta(hours=25),
            state_before={"status": "open"},
            state_after={"status": "resolved"},
            can_undo=True,
            undo_window_hours=24,
        )
        
        undo_manager._snapshots["snap_expired"] = snapshot
        undo_manager._undo_stack["company_123"] = ["snap_expired"]
        
        result = await undo_manager.undo("snap_expired")
        
        assert result["success"] is False
        assert result["status"] == UndoStatus.EXPIRED.value
    
    @pytest.mark.asyncio
    async def test_undo_already_restored_snapshot(self, undo_manager):
        """Test undo of already restored snapshot."""
        snapshot = await undo_manager.create_snapshot({
            "action_type": "ticket_status_change",
            "company_id": "company_123",
            "performed_by": "user_456",
            "state_before": {"status": "open"},
            "state_after": {"status": "resolved"},
        })
        
        # First undo
        result1 = await undo_manager.undo(snapshot.snapshot_id)
        assert result1["success"] is True
        
        # Second undo (should fail)
        result2 = await undo_manager.undo(snapshot.snapshot_id)
        assert result2["success"] is False
    
    @pytest.mark.asyncio
    async def test_restoration_by_action_type(self, undo_manager):
        """Test restoration for different action types."""
        # Ticket assignment
        snapshot1 = await undo_manager.create_snapshot({
            "action_type": "ticket_assignment",
            "company_id": "company_123",
            "performed_by": "user_456",
            "state_before": {"assignee": "agent_a"},
            "state_after": {"assignee": "agent_b"},
        })
        
        result1 = await undo_manager.undo(snapshot1.snapshot_id)
        assert result1["success"] is True
        assert result1["restoration_result"]["field"] == "assignee"
        
        # Knowledge update
        snapshot2 = await undo_manager.create_snapshot({
            "action_type": "knowledge_update",
            "company_id": "company_123",
            "performed_by": "user_456",
            "state_before": {"content": "old content", "entry_id": "kb_123"},
            "state_after": {"content": "new content", "entry_id": "kb_123"},
        })
        
        result2 = await undo_manager.undo(snapshot2.snapshot_id)
        assert result2["success"] is True
        assert "restored_content" in result2["restoration_result"]


class TestMultiLevelUndo:
    """Test multi-level undo functionality."""
    
    @pytest.fixture
    def undo_manager(self):
        """Create an UndoManager instance."""
        return UndoManager(config=UndoConfig(max_undo_levels=10))
    
    @pytest.mark.asyncio
    async def test_multi_level_undo_single(self, undo_manager):
        """Test single level undo."""
        company_id = "company_123"
        
        # Create multiple snapshots
        for i in range(3):
            await undo_manager.create_snapshot({
                "action_type": "ticket_status_change",
                "company_id": company_id,
                "performed_by": "user_456",
                "state_before": {"status": f"status_{i}"},
                "state_after": {"status": f"status_{i+1}"},
            })
        
        # Undo one level
        results = await undo_manager.undo_multi_level(company_id, levels=1)
        
        assert len(results) == 1
        assert results[0]["success"] is True
    
    @pytest.mark.asyncio
    async def test_multi_level_undo_multiple(self, undo_manager):
        """Test multiple level undo."""
        company_id = "company_123"
        
        # Create multiple snapshots
        for i in range(5):
            await undo_manager.create_snapshot({
                "action_type": "ticket_status_change",
                "company_id": company_id,
                "performed_by": "user_456",
                "state_before": {"status": f"status_{i}"},
                "state_after": {"status": f"status_{i+1}"},
            })
        
        # Undo 3 levels
        results = await undo_manager.undo_multi_level(company_id, levels=3)
        
        assert len(results) == 3
        assert all(r["success"] for r in results)
    
    @pytest.mark.asyncio
    async def test_multi_level_undo_stops_on_failure(self, undo_manager):
        """Test that multi-level undo stops on failure."""
        company_id = "company_123"
        
        # Create some snapshots
        for i in range(3):
            await undo_manager.create_snapshot({
                "action_type": "ticket_status_change",
                "company_id": company_id,
                "performed_by": "user_456",
                "state_before": {"status": f"status_{i}"},
                "state_after": {"status": f"status_{i+1}"},
            })
        
        # Undo all, should get all 3
        results = await undo_manager.undo_multi_level(company_id, levels=5)
        
        # Should only have undone 3 (the actual number available)
        assert len(results) == 3
    
    @pytest.mark.asyncio
    async def test_undo_group(self, undo_manager):
        """Test undoing a group of actions atomically."""
        company_id = "company_123"
        
        # Create a group
        group_id = undo_manager.create_group(
            company_id=company_id,
            description="Multi-step update"
        )
        
        # Add actions to group
        await undo_manager.create_snapshot({
            "action_type": "ticket_status_change",
            "company_id": company_id,
            "performed_by": "user_456",
            "state_before": {"status": "open"},
            "state_after": {"status": "in_progress"},
            "group_id": group_id,
        })
        
        await undo_manager.create_snapshot({
            "action_type": "ticket_assignment",
            "company_id": company_id,
            "performed_by": "user_456",
            "state_before": {"assignee": None},
            "state_after": {"assignee": "agent_123"},
            "group_id": group_id,
        })
        
        # Undo the group
        results = await undo_manager.undo_group(group_id)
        
        assert len(results) == 2
        assert all(r["success"] for r in results)


class TestConcurrentOperations:
    """Test concurrent operation handling."""
    
    @pytest.fixture
    def undo_manager(self):
        """Create an UndoManager instance."""
        return UndoManager(config=UndoConfig(concurrent_undo_timeout_seconds=5))
    
    @pytest.mark.asyncio
    async def test_concurrent_undo_same_company(self, undo_manager):
        """Test concurrent undo operations for same company."""
        company_id = "company_123"
        
        # Create multiple snapshots
        snapshots = []
        for i in range(3):
            snapshot = await undo_manager.create_snapshot({
                "action_type": "ticket_status_change",
                "company_id": company_id,
                "performed_by": "user_456",
                "state_before": {"status": f"status_{i}"},
                "state_after": {"status": f"status_{i+1}"},
            })
            snapshots.append(snapshot)
        
        # Undo all concurrently
        tasks = [
            undo_manager.undo(s.snapshot_id)
            for s in snapshots
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All should complete (some may fail due to lock ordering)
        assert len(results) == 3
    
    @pytest.mark.asyncio
    async def test_concurrent_undo_different_companies(self, undo_manager):
        """Test concurrent undo operations for different companies."""
        # Create snapshots for different companies
        snapshots = []
        for i in range(3):
            snapshot = await undo_manager.create_snapshot({
                "action_type": "ticket_status_change",
                "company_id": f"company_{i}",
                "performed_by": "user_456",
                "state_before": {"status": "open"},
                "state_after": {"status": "resolved"},
            })
            snapshots.append(snapshot)
        
        # Undo all concurrently
        tasks = [
            undo_manager.undo(s.snapshot_id)
            for s in snapshots
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All should succeed (different companies, no lock contention)
        assert all(r["success"] for r in results)
    
    @pytest.mark.asyncio
    async def test_custom_restoration_handler(self, undo_manager):
        """Test custom restoration handler."""
        async def custom_handler(state: dict) -> dict:
            return {"custom_restored": True, "data": state}
        
        undo_manager.register_restoration_handler("custom_restore", custom_handler)
        
        snapshot = await undo_manager.create_snapshot({
            "action_type": "ticket_status_change",
            "company_id": "company_123",
            "performed_by": "user_456",
            "state_before": {"custom": "state"},
            "state_after": {"custom": "updated"},
            "restoration_handler": "custom_restore",
        })
        
        result = await undo_manager.undo(snapshot.snapshot_id)
        
        assert result["success"] is True
        assert result["restoration_result"]["custom_restored"] is True


class TestConflictDetection:
    """Test conflict detection during undo."""
    
    @pytest.fixture
    def undo_manager(self):
        """Create an UndoManager instance."""
        return UndoManager(config=UndoConfig())
    
    @pytest.mark.asyncio
    async def test_conflict_detection_newer_snapshot(self, undo_manager):
        """Test conflict detection when newer changes exist."""
        company_id = "company_123"
        entity_id = "ticket_456"
        
        # Create first snapshot
        snapshot1 = await undo_manager.create_snapshot({
            "action_type": "ticket_status_change",
            "company_id": company_id,
            "performed_by": "user_456",
            "state_before": {"status": "open", "entity_id": entity_id},
            "state_after": {"status": "resolved", "entity_id": entity_id},
        })
        
        # Create newer snapshot for same entity
        snapshot2 = await undo_manager.create_snapshot({
            "action_type": "ticket_status_change",
            "company_id": company_id,
            "performed_by": "user_456",
            "state_before": {"status": "resolved", "entity_id": entity_id},
            "state_after": {"status": "closed", "entity_id": entity_id},
        })
        
        # Try to undo older snapshot (should detect conflict)
        result = await undo_manager.undo(snapshot1.snapshot_id)
        
        assert result["success"] is False
        assert result["status"] == UndoStatus.CONFLICT.value
    
    @pytest.mark.asyncio
    async def test_force_undo_bypasses_conflict(self, undo_manager):
        """Test that force undo bypasses conflict detection."""
        company_id = "company_123"
        entity_id = "ticket_456"
        
        # Create first snapshot
        snapshot1 = await undo_manager.create_snapshot({
            "action_type": "ticket_status_change",
            "company_id": company_id,
            "performed_by": "user_456",
            "state_before": {"status": "open", "entity_id": entity_id},
            "state_after": {"status": "resolved", "entity_id": entity_id},
        })
        
        # Create newer snapshot
        await undo_manager.create_snapshot({
            "action_type": "ticket_status_change",
            "company_id": company_id,
            "performed_by": "user_456",
            "state_before": {"status": "resolved", "entity_id": entity_id},
            "state_after": {"status": "closed", "entity_id": entity_id},
        })
        
        # Force undo older snapshot
        result = await undo_manager.undo(snapshot1.snapshot_id, force=True)
        
        assert result["success"] is True


class TestUndoManagerUtilities:
    """Test utility methods."""
    
    @pytest.fixture
    def undo_manager(self):
        """Create an UndoManager instance."""
        return UndoManager(config=UndoConfig())
    
    @pytest.mark.asyncio
    async def test_get_undoable_actions(self, undo_manager):
        """Test getting list of undoable actions."""
        company_id = "company_123"
        
        # Create some actions
        for i in range(5):
            await undo_manager.create_snapshot({
                "action_type": "ticket_status_change",
                "company_id": company_id,
                "performed_by": "user_456",
                "state_before": {"status": f"status_{i}"},
                "state_after": {"status": f"status_{i+1}"},
            })
        
        # Add a financial action (should not appear)
        await undo_manager.create_snapshot({
            "action_type": "refund",
            "company_id": company_id,
            "performed_by": "user_456",
            "state_before": {},
            "state_after": {},
        })
        
        actions = undo_manager.get_undoable_actions(company_id)
        
        assert len(actions) == 5  # Only non-financial actions
    
    @pytest.mark.asyncio
    async def test_get_stats(self, undo_manager):
        """Test getting statistics."""
        await undo_manager.create_snapshot({
            "action_type": "ticket_status_change",
            "company_id": "company_123",
            "performed_by": "user_456",
            "state_before": {},
            "state_after": {},
        })
        
        stats = undo_manager.get_stats()
        
        assert stats["total_snapshots"] == 1
        assert stats["active_snapshots"] == 1
        assert "company_123" in stats["undo_stacks"]
    
    @pytest.mark.asyncio
    async def test_cleanup_expired(self, undo_manager):
        """Test cleanup of expired snapshots."""
        # Add an expired snapshot manually
        expired_snapshot = UndoSnapshot(
            snapshot_id="snap_expired",
            action_type=UndoableActionType.TICKET_STATUS_CHANGE,
            company_id="company_123",
            performed_by="user_456",
            created_at=datetime.now(timezone.utc) - timedelta(hours=25),
            state_before={},
            state_after={},
            can_undo=True,
            undo_window_hours=24,
        )
        
        undo_manager._snapshots["snap_expired"] = expired_snapshot
        
        cleaned = await undo_manager.cleanup_expired()
        
        assert cleaned == 1
        assert expired_snapshot.status == SnapshotStatus.EXPIRED
    
    def test_is_action_financial(self, undo_manager):
        """Test financial action check."""
        assert undo_manager.is_action_financial("refund") is True
        assert undo_manager.is_action_financial("charge") is True
        assert undo_manager.is_action_financial("payment") is True
        assert undo_manager.is_action_financial("ticket_status_change") is False
        assert undo_manager.is_action_financial("knowledge_update") is False


class TestUndoConfig:
    """Test UndoConfig validation."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = UndoConfig()
        
        assert config.max_undo_levels == 10
        assert config.default_undo_window_hours == 24
        assert config.max_snapshot_size_kb == 100
        assert config.enable_auto_cleanup is True
    
    def test_custom_config(self):
        """Test custom configuration values."""
        config = UndoConfig(
            max_undo_levels=50,
            default_undo_window_hours=48,
            max_snapshot_size_kb=500,
        )
        
        assert config.max_undo_levels == 50
        assert config.default_undo_window_hours == 48
        assert config.max_snapshot_size_kb == 500
    
    def test_config_validation(self):
        """Test configuration validation."""
        # Valid range
        config = UndoConfig(max_undo_levels=100)
        assert config.max_undo_levels == 100
        
        # Invalid - too low
        with pytest.raises(ValueError):
            UndoConfig(max_undo_levels=0)
        
        # Invalid - too high
        with pytest.raises(ValueError):
            UndoConfig(max_undo_levels=200)
