"""
Unit tests for PARWA Undo Manager Service.

Tests cover:
- UndoManager: Main undo manager service
- SnapshotSerializer: State snapshot serialization
- SnapshotStorage: Snapshot storage and retrieval
- StateRestorer: State restoration with validation

Key test cases:
- Creates undo snapshot
- Snapshot serializes state
- Restore reverts to previous state
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio

# Import the modules to test
from backend.services.undo_manager import (
    UndoManager,
    ActionType,
    ActionCategory,
    UndoStatus,
    SnapshotStatus,
    ActionSnapshot,
    ActionHistory,
    get_undo_manager,
)

from backend.services.undo_manager.snapshot import (
    SnapshotSerializer,
    SnapshotStorage,
    SnapshotType,
    CompressionType,
    SnapshotMetadata,
    StateSnapshot,
    get_snapshot_serializer,
    get_snapshot_storage,
)

from backend.services.undo_manager.restore import (
    StateValidator,
    StateRestorer,
    RestorationStatus,
    RestorationType,
    ValidationLevel,
    ValidationResult,
    get_state_validator,
    get_state_restorer,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def undo_manager():
    """Create a fresh UndoManager instance for each test."""
    return UndoManager(max_undo_levels=10)


@pytest.fixture
def snapshot_serializer():
    """Create a SnapshotSerializer instance."""
    return SnapshotSerializer()


@pytest.fixture
def snapshot_storage(snapshot_serializer):
    """Create a SnapshotStorage instance."""
    return SnapshotStorage(serializer=snapshot_serializer)


@pytest.fixture
def state_validator():
    """Create a StateValidator instance."""
    return StateValidator(validation_level=ValidationLevel.BASIC)


@pytest.fixture
def state_restorer(state_validator):
    """Create a StateRestorer instance."""
    return StateRestorer(validator=state_validator)


# ============================================================================
# UndoManager Tests
# ============================================================================

class TestUndoManager:
    """Tests for UndoManager class."""

    @pytest.mark.asyncio
    async def test_create_snapshot(self, undo_manager):
        """Test that create_snapshot creates undo snapshot."""
        result = await undo_manager.create_snapshot({
            "action_type": "ticket_status_change",
            "company_id": "comp_123",
            "state_data": {
                "ticket_id": "t_456",
                "status": "open",
                "assignee": "user_789",
            },
            "metadata": {"reason": "User request"},
        })

        assert "snapshot_id" in result
        assert result["action_type"] == "ticket_status_change"
        assert result["company_id"] == "comp_123"
        assert "created_at" in result
        assert "expires_at" in result

    @pytest.mark.asyncio
    async def test_create_snapshot_financial_action(self, undo_manager):
        """Test that financial actions are categorized correctly."""
        result = await undo_manager.create_snapshot({
            "action_type": "refund",
            "company_id": "comp_123",
            "state_data": {"amount": 100.00},
        })

        assert result["category"] == "financial"

    @pytest.mark.asyncio
    async def test_track_action(self, undo_manager):
        """Test that track_action tracks action with timestamp."""
        result = await undo_manager.track_action({
            "action_type": "ticket_status_change",
            "company_id": "comp_123",
            "performed_by": "user_789",
            "snapshot_id": "snap_001",
            "metadata": {"old_status": "open", "new_status": "closed"},
        })

        assert "action_id" in result
        assert result["action_type"] == "ticket_status_change"
        assert result["can_undo"] is True
        assert "tracked_at" in result
        assert "undo_expires_at" in result

    @pytest.mark.asyncio
    async def test_track_financial_action_not_undoable(self, undo_manager):
        """Test that financial actions are tracked but not undoable."""
        result = await undo_manager.track_action({
            "action_type": "refund",
            "company_id": "comp_123",
            "performed_by": "user_789",
            "amount": 100.00,
        })

        assert result["is_financial"] is True
        assert result["can_undo"] is False

    @pytest.mark.asyncio
    async def test_undo_action_success(self, undo_manager):
        """Test successful undo of non-financial action."""
        # Create snapshot first
        snapshot = await undo_manager.create_snapshot({
            "action_type": "ticket_status_change",
            "company_id": "comp_123",
            "state_data": {
                "ticket_id": "t_456",
                "status": "open",
            },
        })

        # Track the action
        action = await undo_manager.track_action({
            "action_id": snapshot["action_id"],
            "action_type": "ticket_status_change",
            "company_id": "comp_123",
            "performed_by": "user_789",
            "snapshot_id": snapshot["snapshot_id"],
        })

        # Undo the action
        result = await undo_manager.undo_action(
            action["action_id"],
            performed_by="user_admin"
        )

        assert result["success"] is True
        assert result["status"] == UndoStatus.COMPLETED.value
        assert "restored_state" in result

    @pytest.mark.asyncio
    async def test_undo_action_financial_not_allowed(self, undo_manager):
        """Test that financial actions cannot be undone."""
        # Track financial action
        action = await undo_manager.track_action({
            "action_type": "refund",
            "company_id": "comp_123",
            "performed_by": "user_789",
            "amount": 100.00,
        })

        # Try to undo
        result = await undo_manager.undo_action(action["action_id"])

        assert result["success"] is False
        assert result["status"] == UndoStatus.NOT_UNDOABLE.value
        assert result["is_financial"] is True

    @pytest.mark.asyncio
    async def test_undo_action_not_found(self, undo_manager):
        """Test undo with invalid action ID."""
        result = await undo_manager.undo_action("nonexistent_action")

        assert result["success"] is False
        assert result["status"] == UndoStatus.FAILED.value
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_get_action_history(self, undo_manager):
        """Test retrieving action history."""
        # Create and track some actions
        for i in range(3):
            await undo_manager.track_action({
                "action_type": "ticket_status_change",
                "company_id": "comp_123",
                "performed_by": f"user_{i}",
            })

        history = await undo_manager.get_action_history("comp_123")

        assert len(history) == 3
        # Should be sorted by performed_at descending
        assert history[0]["performed_at"] >= history[1]["performed_at"]

    @pytest.mark.asyncio
    async def test_get_undoable_actions(self, undo_manager):
        """Test getting list of undoable actions."""
        # Create undoable and non-undoable actions
        await undo_manager.track_action({
            "action_type": "ticket_status_change",
            "company_id": "comp_123",
            "performed_by": "user_1",
        })

        await undo_manager.track_action({
            "action_type": "refund",  # Financial - not undoable
            "company_id": "comp_123",
            "performed_by": "user_2",
        })

        undoable = await undo_manager.get_undoable_actions("comp_123")

        assert len(undoable) == 1
        assert undoable[0]["action_type"] == "ticket_status_change"

    def test_is_action_financial(self, undo_manager):
        """Test checking if action is financial."""
        assert undo_manager.is_action_financial("refund") is True
        assert undo_manager.is_action_financial("charge") is True
        assert undo_manager.is_action_financial("payment") is True
        assert undo_manager.is_action_financial("ticket_status_change") is False

    @pytest.mark.asyncio
    async def test_max_undo_levels_enforced(self):
        """Test that max undo levels are enforced."""
        manager = UndoManager(max_undo_levels=3)

        # Create more actions than max
        for i in range(5):
            await manager.track_action({
                "action_type": "ticket_status_change",
                "company_id": "comp_123",
                "performed_by": f"user_{i}",
            })

        history = await manager.get_action_history("comp_123")

        # Should only have 3 (max_undo_levels)
        assert len(history) == 3

    @pytest.mark.asyncio
    async def test_register_undo_handler(self, undo_manager):
        """Test registering custom undo handler."""
        custom_handler_called = False

        async def custom_handler(action, snapshot):
            nonlocal custom_handler_called
            custom_handler_called = True
            return {"restored_state": {"custom": True}}

        undo_manager.register_undo_handler(
            ActionType.TICKET_STATUS_CHANGE,
            custom_handler
        )

        # Create and track action
        snapshot = await undo_manager.create_snapshot({
            "action_type": "ticket_status_change",
            "company_id": "comp_123",
            "state_data": {"test": "data"},
        })

        action = await undo_manager.track_action({
            "action_id": snapshot["action_id"],
            "action_type": "ticket_status_change",
            "company_id": "comp_123",
            "performed_by": "user_1",
            "snapshot_id": snapshot["snapshot_id"],
        })

        await undo_manager.undo_action(action["action_id"])

        assert custom_handler_called is True


# ============================================================================
# SnapshotSerializer Tests
# ============================================================================

class TestSnapshotSerializer:
    """Tests for SnapshotSerializer class."""

    def test_serialize_state(self, snapshot_serializer):
        """Test that snapshot serializes state to JSON."""
        state = {
            "ticket_id": "t_123",
            "status": "open",
            "assignee": "user_456",
        }

        serialized = snapshot_serializer.serialize(state)

        assert isinstance(serialized, str)
        assert "ticket_id" in serialized
        assert "t_123" in serialized

    def test_serialize_with_datetime(self, snapshot_serializer):
        """Test serialization handles datetime objects."""
        state = {
            "created_at": datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            "data": "test",
        }

        serialized = snapshot_serializer.serialize(state)
        deserialized = snapshot_serializer.deserialize(serialized)

        assert isinstance(deserialized["created_at"], datetime)
        assert deserialized["created_at"].year == 2024

    def test_serialize_with_set(self, snapshot_serializer):
        """Test serialization handles set objects."""
        state = {
            "tags": {"urgent", "customer", "priority"},
            "id": "123",
        }

        serialized = snapshot_serializer.serialize(state)
        deserialized = snapshot_serializer.deserialize(serialized)

        assert isinstance(deserialized["tags"], set)
        assert "urgent" in deserialized["tags"]

    def test_deserialize_state(self, snapshot_serializer):
        """Test deserializing state from JSON."""
        state = {
            "id": "test_123",
            "name": "Test Item",
            "count": 42,
        }

        serialized = snapshot_serializer.serialize(state)
        deserialized = snapshot_serializer.deserialize(serialized)

        assert deserialized == state

    def test_compression_applied_for_large_state(self, snapshot_serializer):
        """Test that compression is applied for large states."""
        # Create a large state object
        large_state = {
            "data": "x" * 5000,  # Large string
            "items": [{"id": i, "data": "item" * 100} for i in range(100)],
        }

        serialized = snapshot_serializer.serialize(large_state)

        # Should be compressed (starts with base64 encoded zlib data)
        # The serialized string should be smaller than original
        assert len(serialized) < len(str(large_state))

    def test_calculate_checksum(self, snapshot_serializer):
        """Test checksum calculation."""
        data1 = '{"test": "data"}'
        data2 = '{"test": "different"}'

        checksum1 = snapshot_serializer.calculate_checksum(data1)
        checksum2 = snapshot_serializer.calculate_checksum(data2)

        assert checksum1 != checksum2
        assert len(checksum1) == 64  # SHA-256 hex digest length

    def test_serialize_exceeds_max_size(self):
        """Test that large states raise error."""
        serializer = SnapshotSerializer(max_snapshot_size=100)

        large_state = {"data": "x" * 200}

        with pytest.raises(ValueError, match="exceeds maximum"):
            serializer.serialize(large_state)


# ============================================================================
# SnapshotStorage Tests
# ============================================================================

class TestSnapshotStorage:
    """Tests for SnapshotStorage class."""

    @pytest.mark.asyncio
    async def test_store_snapshot(self, snapshot_storage):
        """Test storing a snapshot."""
        snapshot_id = await snapshot_storage.store({
            "company_id": "comp_123",
            "action_type": "ticket_status_change",
            "state_data": {
                "ticket_id": "t_456",
                "status": "open",
            },
        })

        assert snapshot_id.startswith("snap_")

    @pytest.mark.asyncio
    async def test_retrieve_snapshot(self, snapshot_storage):
        """Test retrieving a stored snapshot."""
        snapshot_id = await snapshot_storage.store({
            "company_id": "comp_123",
            "action_type": "ticket_status_change",
            "state_data": {"ticket_id": "t_456", "status": "open"},
        })

        retrieved = await snapshot_storage.retrieve(snapshot_id)

        assert retrieved is not None
        assert retrieved["snapshot_id"] == snapshot_id
        assert retrieved["state_data"]["ticket_id"] == "t_456"

    @pytest.mark.asyncio
    async def test_retrieve_nonexistent_snapshot(self, snapshot_storage):
        """Test retrieving a nonexistent snapshot."""
        result = await snapshot_storage.retrieve("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_snapshot(self, snapshot_storage):
        """Test deleting a snapshot."""
        snapshot_id = await snapshot_storage.store({
            "company_id": "comp_123",
            "action_type": "test",
            "state_data": {"test": "data"},
        })

        deleted = await snapshot_storage.delete(snapshot_id)
        assert deleted is True

        # Verify it's gone
        retrieved = await snapshot_storage.retrieve(snapshot_id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_list_snapshots(self, snapshot_storage):
        """Test listing snapshots for a company."""
        # Create multiple snapshots
        for i in range(3):
            await snapshot_storage.store({
                "company_id": "comp_123",
                "action_type": f"action_{i}",
                "state_data": {"index": i},
            })

        # Create snapshot for different company
        await snapshot_storage.store({
            "company_id": "comp_456",
            "action_type": "other_action",
            "state_data": {"other": True},
        })

        snapshots = await snapshot_storage.list_snapshots("comp_123")

        assert len(snapshots) == 3

    @pytest.mark.asyncio
    async def test_create_incremental_snapshot(self, snapshot_storage):
        """Test creating incremental snapshot."""
        parent_id = await snapshot_storage.store({
            "company_id": "comp_123",
            "action_type": "test",
            "state_data": {"field1": "value1", "field2": "value2"},
        })

        incremental_id = await snapshot_storage.create_incremental_snapshot(
            company_id="comp_123",
            action_type="test_update",
            parent_snapshot_id=parent_id,
            new_state={"field1": "value1_updated", "field2": "value2", "field3": "new"},
        )

        assert incremental_id.startswith("snap_")
        assert incremental_id != parent_id

    @pytest.mark.asyncio
    async def test_get_storage_stats(self, snapshot_storage):
        """Test getting storage statistics."""
        await snapshot_storage.store({
            "company_id": "comp_123",
            "action_type": "test",
            "state_data": {"test": "data"},
        })

        stats = await snapshot_storage.get_storage_stats()

        assert "total_snapshots" in stats
        assert stats["total_snapshots"] >= 1
        assert "total_size_bytes" in stats

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, snapshot_storage):
        """Test cleanup of expired snapshots."""
        # Create snapshot with short retention
        storage = SnapshotStorage(retention_days=0)  # Expired immediately

        snapshot_id = await storage.store({
            "company_id": "comp_123",
            "action_type": "test",
            "state_data": {"test": "data"},
        })

        # Manually expire it
        snapshot = storage._snapshots[snapshot_id]
        snapshot.metadata.expires_at = datetime.now(timezone.utc) - timedelta(days=1)

        result = await storage.cleanup_expired()

        assert result["expired_count"] >= 1


# ============================================================================
# StateValidator Tests
# ============================================================================

class TestStateValidator:
    """Tests for StateValidator class."""

    @pytest.mark.asyncio
    async def test_validate_basic_success(self, state_validator):
        """Test basic validation passes for valid states."""
        result = await state_validator.validate_for_restoration(
            current_state={"id": "123", "status": "open"},
            target_state={"id": "123", "status": "closed"},
            context={"company_id": "comp_123"},
        )

        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_validate_missing_required_key(self, state_validator):
        """Test validation fails for missing required key."""
        result = await state_validator.validate_for_restoration(
            current_state={"id": "123", "status": "open"},
            target_state={"status": "closed"},  # Missing 'id'
            context={"company_id": "comp_123"},
        )

        assert result.is_valid is False
        assert any("required key" in e.lower() for e in result.errors)

    @pytest.mark.asyncio
    async def test_validate_financial_changes_blocked(self, state_validator):
        """Test that financial changes are blocked."""
        result = await state_validator.validate_for_restoration(
            current_state={"id": "123", "amount": 100.00},
            target_state={"id": "123", "amount": 50.00},  # Financial change
            context={"company_id": "comp_123"},
        )

        assert result.is_valid is True  # Basic validation passes
        assert any("financial" in r.lower() for r in result.blocked_reasons)

    @pytest.mark.asyncio
    async def test_validate_none_level(self):
        """Test validation with NONE level skips all checks."""
        validator = StateValidator(validation_level=ValidationLevel.NONE)

        result = await validator.validate_for_restoration(
            current_state={"status": "open"},
            target_state={},  # Would normally fail
            context={},
        )

        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_validate_strict_type_mismatch(self):
        """Test strict validation catches type mismatches."""
        validator = StateValidator(validation_level=ValidationLevel.STRICT)

        result = await validator.validate_for_restoration(
            current_state={"count": 42},
            target_state={"count": "42"},  # String instead of int
            context={},
        )

        assert result.is_valid is False
        assert any("type mismatch" in e.lower() for e in result.errors)

    @pytest.mark.asyncio
    async def test_register_custom_validator(self, state_validator):
        """Test registering custom validator."""
        async def custom_validator(current, target, context):
            return ValidationResult(
                is_valid=False,
                errors=["Custom validation failed"],
            )

        state_validator.register_validator("custom_action", custom_validator)

        result = await state_validator.validate_for_restoration(
            current_state={},
            target_state={},
            context={"action_type": "custom_action"},
        )

        assert result.is_valid is False
        assert "Custom validation failed" in result.errors


# ============================================================================
# StateRestorer Tests
# ============================================================================

class TestStateRestorer:
    """Tests for StateRestorer class."""

    @pytest.mark.asyncio
    async def test_validate_and_restore_success(self, state_restorer):
        """Test successful state restoration."""
        result = await state_restorer.validate_and_restore({
            "snapshot_id": "snap_123",
            "action_id": "action_456",
            "company_id": "comp_789",
            "current_state": {"id": "123", "status": "closed"},
            "target_state": {"id": "123", "status": "open"},
            "performed_by": "user_admin",
        })

        assert result["success"] is True
        assert result["status"] == RestorationStatus.COMPLETED.value
        assert "restored_state" in result

    @pytest.mark.asyncio
    async def test_restore_reverts_to_previous_state(self, state_restorer):
        """Test that restore reverts to previous state."""
        current_state = {
            "id": "t_123",
            "status": "closed",
            "assignee": "user_new",
        }

        target_state = {
            "id": "t_123",
            "status": "open",
            "assignee": "user_old",
        }

        result = await state_restorer.validate_and_restore({
            "snapshot_id": "snap_123",
            "action_id": "action_456",
            "company_id": "comp_789",
            "current_state": current_state,
            "target_state": target_state,
            "performed_by": "user_admin",
        })

        assert result["success"] is True
        assert result["restored_state"]["status"] == "open"
        assert result["restored_state"]["assignee"] == "user_old"

    @pytest.mark.asyncio
    async def test_restore_validation_failure(self, state_restorer):
        """Test restoration fails when validation fails."""
        # Use strict validator
        validator = StateValidator(validation_level=ValidationLevel.STRICT)
        restorer = StateRestorer(validator=validator)

        result = await restorer.validate_and_restore({
            "snapshot_id": "snap_123",
            "action_id": "action_456",
            "company_id": "comp_789",
            "current_state": {"count": 42},
            "target_state": {"count": "42"},  # Type mismatch
            "performed_by": "user_admin",
        })

        assert result["success"] is False
        assert result["status"] == RestorationStatus.FAILED.value

    @pytest.mark.asyncio
    async def test_partial_restoration(self, state_restorer):
        """Test partial state restoration."""
        current_state = {
            "id": "123",
            "status": "closed",
            "priority": "high",
            "assignee": "user_new",
        }

        target_state = {
            "id": "123",
            "status": "open",
            "priority": "low",
            "assignee": "user_old",
        }

        result = await state_restorer.validate_and_restore({
            "snapshot_id": "snap_123",
            "action_id": "action_456",
            "company_id": "comp_789",
            "current_state": current_state,
            "target_state": target_state,
            "performed_by": "user_admin",
            "restoration_type": "partial",
            "keys_to_restore": ["status"],  # Only restore status
        })

        assert result["success"] is True
        # Only status should be restored, priority stays
        assert result["restored_state"]["status"] == "open"
        assert result["restored_state"]["priority"] == "high"  # Unchanged

    @pytest.mark.asyncio
    async def test_get_restoration_attempt(self, state_restorer):
        """Test getting restoration attempt details."""
        result = await state_restorer.validate_and_restore({
            "snapshot_id": "snap_123",
            "action_id": "action_456",
            "company_id": "comp_789",
            "current_state": {"id": "123"},
            "target_state": {"id": "123", "extra": "data"},
            "performed_by": "user_admin",
        })

        attempt_id = result["attempt_id"]
        attempt = await state_restorer.get_restoration_attempt(attempt_id)

        assert attempt is not None
        assert attempt["snapshot_id"] == "snap_123"
        assert attempt["company_id"] == "comp_789"

    @pytest.mark.asyncio
    async def test_get_restoration_history(self, state_restorer):
        """Test getting restoration history."""
        # Create multiple restorations
        for i in range(3):
            await state_restorer.validate_and_restore({
                "snapshot_id": f"snap_{i}",
                "action_id": f"action_{i}",
                "company_id": "comp_123",
                "current_state": {"id": str(i)},
                "target_state": {"id": str(i), "updated": True},
                "performed_by": f"user_{i}",
            })

        history = await state_restorer.get_restoration_history("comp_123")

        assert len(history) == 3

    @pytest.mark.asyncio
    async def test_register_restoration_handler(self, state_restorer):
        """Test registering custom restoration handler."""
        handler_called = False

        async def custom_handler(current, target, data):
            nonlocal handler_called
            handler_called = True
            return {"success": True, "restored_state": {"custom": True}}

        state_restorer.register_restoration_handler("custom_action", custom_handler)

        result = await state_restorer.validate_and_restore({
            "snapshot_id": "snap_123",
            "action_id": "action_456",
            "company_id": "comp_789",
            "action_type": "custom_action",
            "current_state": {},
            "target_state": {},
        })

        assert handler_called is True
        assert result["restored_state"]["custom"] is True


# ============================================================================
# Integration Tests
# ============================================================================

class TestUndoManagerIntegration:
    """Integration tests for the complete undo flow."""

    @pytest.mark.asyncio
    async def test_complete_undo_flow(self):
        """Test complete flow: snapshot -> track -> undo."""
        manager = UndoManager()

        # 1. Create snapshot before risky action
        snapshot = await manager.create_snapshot({
            "action_type": "ticket_status_change",
            "company_id": "comp_123",
            "state_data": {
                "ticket_id": "t_456",
                "status": "open",
                "assignee": "user_original",
            },
            "metadata": {"reason": "Status change requested"},
        })

        assert snapshot["snapshot_id"] is not None

        # 2. Track the action
        action = await manager.track_action({
            "action_id": snapshot["action_id"],
            "action_type": "ticket_status_change",
            "company_id": "comp_123",
            "performed_by": "user_agent",
            "snapshot_id": snapshot["snapshot_id"],
            "metadata": {
                "old_status": "open",
                "new_status": "closed",
            },
        })

        assert action["can_undo"] is True

        # 3. Later, undo the action
        undo_result = await manager.undo_action(
            action["action_id"],
            performed_by="user_admin"
        )

        assert undo_result["success"] is True
        assert undo_result["status"] == UndoStatus.COMPLETED.value

        # 4. Verify action is marked as undone
        history = await manager.get_action_history("comp_123")
        assert history[0]["is_undone"] is True

    @pytest.mark.asyncio
    async def test_financial_action_protection(self):
        """Test that financial actions are protected from simple undo."""
        manager = UndoManager()

        # Create snapshot for financial action
        snapshot = await manager.create_snapshot({
            "action_type": "refund",
            "company_id": "comp_123",
            "state_data": {
                "order_id": "o_789",
                "amount": 100.00,
            },
        })

        # Track the action
        action = await manager.track_action({
            "action_id": snapshot["action_id"],
            "action_type": "refund",
            "company_id": "comp_123",
            "performed_by": "user_agent",
            "snapshot_id": snapshot["snapshot_id"],
            "amount": 100.00,
        })

        assert action["is_financial"] is True
        assert action["can_undo"] is False

        # Attempt to undo
        undo_result = await manager.undo_action(action["action_id"])

        assert undo_result["success"] is False
        assert undo_result["status"] == UndoStatus.NOT_UNDOABLE.value


# ============================================================================
# Factory Function Tests
# ============================================================================

class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_get_undo_manager_singleton(self):
        """Test get_undo_manager returns singleton."""
        from backend.services.undo_manager import _undo_manager

        # Reset singleton
        import backend.services.undo_manager as module
        module._undo_manager = None

        manager1 = get_undo_manager()
        manager2 = get_undo_manager()

        assert manager1 is manager2

    def test_get_snapshot_serializer_singleton(self):
        """Test get_snapshot_serializer returns singleton."""
        from backend.services.undo_manager.snapshot import _serializer

        import backend.services.undo_manager.snapshot as module
        module._serializer = None

        serializer1 = get_snapshot_serializer()
        serializer2 = get_snapshot_serializer()

        assert serializer1 is serializer2

    def test_get_snapshot_storage_singleton(self):
        """Test get_snapshot_storage returns singleton."""
        from backend.services.undo_manager.snapshot import _storage

        import backend.services.undo_manager.snapshot as module
        module._storage = None

        storage1 = get_snapshot_storage()
        storage2 = get_snapshot_storage()

        assert storage1 is storage2

    def test_get_state_restorer_singleton(self):
        """Test get_state_restorer returns singleton."""
        from backend.services.undo_manager.restore import _restorer

        import backend.services.undo_manager.restore as module
        module._restorer = None

        restorer1 = get_state_restorer()
        restorer2 = get_state_restorer()

        assert restorer1 is restorer2
