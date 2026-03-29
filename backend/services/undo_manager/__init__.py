"""
PARWA Undo Manager Package.

Provides undo capabilities with state snapshot and restoration services.

Modules:
- snapshot: State snapshot serialization and storage
- restore: State restoration with validation
"""

from backend.services.undo_manager.snapshot import (
    SnapshotSerializer,
    SnapshotStorage,
    SnapshotType,
    CompressionType,
    SnapshotStorageStatus,
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
    RestorationAttempt,
    get_state_validator,
    get_state_restorer,
)

__all__ = [
    # Snapshot module
    "SnapshotSerializer",
    "SnapshotStorage",
    "SnapshotType",
    "CompressionType",
    "SnapshotStorageStatus",
    "SnapshotMetadata",
    "StateSnapshot",
    "get_snapshot_serializer",
    "get_snapshot_storage",
    # Restore module
    "StateValidator",
    "StateRestorer",
    "RestorationStatus",
    "RestorationType",
    "ValidationLevel",
    "ValidationResult",
    "RestorationAttempt",
    "get_state_validator",
    "get_state_restorer",
]
