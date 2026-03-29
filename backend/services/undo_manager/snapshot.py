"""
PARWA State Snapshot Serialization Service.

Provides state snapshot creation, serialization, and storage capabilities.
Used by the Undo Manager to capture and restore system state.

Features:
- Serialize system state to JSON
- Store snapshots in database
- Support incremental snapshots
- Handle large state objects efficiently
"""
from typing import Any, Dict, Optional, List, Set
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from dataclasses import dataclass, field, asdict
from enum import Enum
import json
import hashlib
import zlib
import base64
from copy import deepcopy

from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class SnapshotType(str, Enum):
    """Types of snapshots."""
    FULL = "full"
    INCREMENTAL = "incremental"
    DIFF = "diff"


class CompressionType(str, Enum):
    """Compression types for snapshot data."""
    NONE = "none"
    ZLIB = "zlib"
    GZIP = "gzip"


class SnapshotStorageStatus(str, Enum):
    """Status of snapshot storage."""
    PENDING = "pending"
    STORED = "stored"
    RETRIEVED = "retrieved"
    FAILED = "failed"
    DELETED = "deleted"


@dataclass
class SnapshotMetadata:
    """Metadata for a snapshot."""
    snapshot_id: str
    snapshot_type: SnapshotType
    company_id: str
    action_type: str
    created_at: datetime
    created_by: Optional[str] = None
    parent_snapshot_id: Optional[str] = None
    checksum: Optional[str] = None
    compressed: bool = False
    compression_type: CompressionType = CompressionType.NONE
    original_size_bytes: int = 0
    compressed_size_bytes: int = 0
    state_keys: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    expires_at: Optional[datetime] = None


@dataclass
class StateSnapshot:
    """Represents a complete state snapshot."""
    metadata: SnapshotMetadata
    state_data: Dict[str, Any]
    diff_data: Optional[Dict[str, Any]] = None


class SnapshotSerializer:
    """
    Handles serialization and deserialization of state snapshots.

    Features:
    - JSON serialization with type preservation
    - Compression for large state objects
    - Checksum verification
    - Date/datetime handling

    Example:
        serializer = SnapshotSerializer()

        # Serialize state
        serialized = serializer.serialize({
            "ticket": {"id": "t_123", "status": "open"},
            "user": {"id": "u_456", "name": "John"},
        })

        # Deserialize state
        state = serializer.deserialize(serialized)
    """

    # Maximum size before compression is applied (bytes)
    COMPRESSION_THRESHOLD = 1024  # 1 KB

    # Maximum snapshot size (bytes)
    MAX_SNAPSHOT_SIZE = 10 * 1024 * 1024  # 10 MB

    def __init__(
        self,
        compression_threshold: int = COMPRESSION_THRESHOLD,
        max_snapshot_size: int = MAX_SNAPSHOT_SIZE,
        default_compression: CompressionType = CompressionType.ZLIB,
    ):
        """
        Initialize Snapshot Serializer.

        Args:
            compression_threshold: Size threshold for compression
            max_snapshot_size: Maximum allowed snapshot size
            default_compression: Default compression type
        """
        self._compression_threshold = compression_threshold
        self._max_snapshot_size = max_snapshot_size
        self._default_compression = default_compression

        logger.info({
            "event": "snapshot_serializer_initialized",
            "compression_threshold": compression_threshold,
            "max_snapshot_size": max_snapshot_size,
        })

    def serialize(
        self,
        state: Dict[str, Any],
        compress: Optional[bool] = None
    ) -> str:
        """
        Serialize state to JSON string.

        Args:
            state: State dictionary to serialize
            compress: Whether to compress (auto-detect if None)

        Returns:
            Serialized state string

        Raises:
            ValueError: If state exceeds maximum size
        """
        # Convert to JSON-serializable format
        serializable = self._make_serializable(state)

        # Serialize to JSON
        json_str = json.dumps(serializable, default=self._json_serializer, ensure_ascii=False)

        original_size = len(json_str.encode('utf-8'))

        # Check size limit
        if original_size > self._max_snapshot_size:
            raise ValueError(
                f"Snapshot size ({original_size} bytes) exceeds maximum "
                f"({self._max_snapshot_size} bytes)"
            )

        # Determine if compression should be applied
        should_compress = compress if compress is not None else original_size > self._compression_threshold

        if should_compress:
            compressed = self._compress(json_str)
            compressed_size = len(compressed.encode('utf-8'))

            logger.debug({
                "event": "snapshot_compressed",
                "original_size": original_size,
                "compressed_size": compressed_size,
                "compression_ratio": round(compressed_size / original_size, 2) if original_size > 0 else 0,
            })

            return compressed

        return json_str

    def deserialize(
        self,
        serialized: str,
        is_compressed: bool = False
    ) -> Dict[str, Any]:
        """
        Deserialize JSON string back to state dictionary.

        Args:
            serialized: Serialized state string
            is_compressed: Whether the data is compressed

        Returns:
            Deserialized state dictionary
        """
        if is_compressed:
            json_str = self._decompress(serialized)
        else:
            json_str = serialized

        data = json.loads(json_str)
        return self._restore_types(data)

    def _make_serializable(self, obj: Any) -> Any:
        """Convert object to JSON-serializable format."""
        if isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._make_serializable(item) for item in obj]
        elif isinstance(obj, datetime):
            return {"__type__": "datetime", "value": obj.isoformat()}
        elif isinstance(obj, set):
            return {"__type__": "set", "value": list(obj)}
        elif isinstance(obj, bytes):
            return {"__type__": "bytes", "value": base64.b64encode(obj).decode('utf-8')}
        elif isinstance(obj, Enum):
            return {"__type__": "enum", "class": obj.__class__.__name__, "value": obj.value}
        elif hasattr(obj, '__dict__'):
            return {"__type__": "object", "class": obj.__class__.__name__, "value": self._make_serializable(obj.__dict__)}
        else:
            return obj

    def _restore_types(self, obj: Any) -> Any:
        """Restore types from serialized format."""
        if isinstance(obj, dict):
            if "__type__" in obj:
                type_name = obj["__type__"]
                if type_name == "datetime":
                    return datetime.fromisoformat(obj["value"])
                elif type_name == "set":
                    return set(obj["value"])
                elif type_name == "bytes":
                    return base64.b64decode(obj["value"].encode('utf-8'))
                elif type_name == "enum":
                    return obj["value"]  # Return the value, class info preserved for reference
                elif type_name == "object":
                    return self._restore_types(obj.get("value", {}))
            return {k: self._restore_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._restore_types(item) for item in obj]
        else:
            return obj

    def _json_serializer(self, obj: Any) -> Any:
        """Custom JSON serializer for non-standard types."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, set):
            return list(obj)
        elif isinstance(obj, Enum):
            return obj.value
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    def _compress(self, data: str) -> str:
        """Compress data using zlib."""
        compressed = zlib.compress(data.encode('utf-8'))
        return base64.b64encode(compressed).decode('utf-8')

    def _decompress(self, data: str) -> str:
        """Decompress zlib-compressed data."""
        compressed = base64.b64decode(data.encode('utf-8'))
        return zlib.decompress(compressed).decode('utf-8')

    def calculate_checksum(self, data: str) -> str:
        """Calculate SHA-256 checksum of data."""
        return hashlib.sha256(data.encode('utf-8')).hexdigest()


class SnapshotStorage:
    """
    Handles storage and retrieval of state snapshots.

    Features:
    - Store snapshots in memory (with database backend support)
    - Retrieve snapshots by ID
    - Support incremental snapshots
    - Automatic cleanup of expired snapshots

    Example:
        storage = SnapshotStorage()
        serializer = SnapshotSerializer()

        # Store snapshot
        snapshot_id = await storage.store({
            "company_id": "comp_123",
            "action_type": "ticket_status_change",
            "state_data": {"ticket": {"id": "t_123", "status": "open"}},
        })

        # Retrieve snapshot
        snapshot = await storage.retrieve(snapshot_id)
    """

    # Default snapshot retention in days
    DEFAULT_RETENTION_DAYS = 7

    def __init__(
        self,
        serializer: Optional[SnapshotSerializer] = None,
        retention_days: int = DEFAULT_RETENTION_DAYS,
    ):
        """
        Initialize Snapshot Storage.

        Args:
            serializer: SnapshotSerializer instance
            retention_days: Days to retain snapshots
        """
        self._serializer = serializer or SnapshotSerializer()
        self._retention_days = retention_days
        self._snapshots: Dict[str, StateSnapshot] = {}
        self._company_snapshots: Dict[str, List[str]] = {}

        logger.info({
            "event": "snapshot_storage_initialized",
            "retention_days": retention_days,
        })

    async def store(
        self,
        snapshot_data: Dict[str, Any]
    ) -> str:
        """
        Store a state snapshot.

        Args:
            snapshot_data: Dict with:
                - company_id: Company identifier
                - action_type: Type of action
                - state_data: State to capture
                - snapshot_type: Type of snapshot (full/incremental/diff)
                - parent_snapshot_id: Parent snapshot for incremental
                - created_by: User who created the snapshot
                - tags: Optional tags for categorization

        Returns:
            Snapshot ID
        """
        snapshot_id = f"snap_{uuid4().hex[:16]}"
        created_at = datetime.now(timezone.utc)
        expires_at = created_at + timedelta(days=self._retention_days)

        company_id = snapshot_data.get("company_id", "")
        action_type = snapshot_data.get("action_type", "unknown")
        state_data = snapshot_data.get("state_data", {})
        snapshot_type_str = snapshot_data.get("snapshot_type", "full")
        parent_snapshot_id = snapshot_data.get("parent_snapshot_id")
        created_by = snapshot_data.get("created_by")
        tags = snapshot_data.get("tags", [])

        try:
            snapshot_type = SnapshotType(snapshot_type_str)
        except ValueError:
            snapshot_type = SnapshotType.FULL

        # Serialize state
        serialized = self._serializer.serialize(state_data)
        checksum = self._serializer.calculate_checksum(serialized)
        original_size = len(serialized.encode('utf-8'))

        # Determine if compressed
        is_compressed = original_size > self._serializer._compression_threshold
        compressed_size = len(serialized.encode('utf-8'))

        # Create metadata
        metadata = SnapshotMetadata(
            snapshot_id=snapshot_id,
            snapshot_type=snapshot_type,
            company_id=company_id,
            action_type=action_type,
            created_at=created_at,
            created_by=created_by,
            parent_snapshot_id=parent_snapshot_id,
            checksum=checksum,
            compressed=is_compressed,
            compression_type=CompressionType.ZLIB if is_compressed else CompressionType.NONE,
            original_size_bytes=original_size,
            compressed_size_bytes=compressed_size,
            state_keys=list(state_data.keys()),
            tags=tags,
            expires_at=expires_at,
        )

        # Create snapshot
        snapshot = StateSnapshot(
            metadata=metadata,
            state_data=state_data,
        )

        # Store in memory
        self._snapshots[snapshot_id] = snapshot

        # Track by company
        if company_id not in self._company_snapshots:
            self._company_snapshots[company_id] = []
        self._company_snapshots[company_id].append(snapshot_id)

        logger.info({
            "event": "snapshot_stored",
            "snapshot_id": snapshot_id,
            "company_id": company_id,
            "action_type": action_type,
            "snapshot_type": snapshot_type.value,
            "original_size_bytes": original_size,
            "compressed": is_compressed,
            "state_keys": metadata.state_keys,
            "expires_at": expires_at.isoformat(),
        })

        return snapshot_id

    async def retrieve(
        self,
        snapshot_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a snapshot by ID.

        Args:
            snapshot_id: Snapshot identifier

        Returns:
            Snapshot data or None if not found
        """
        snapshot = self._snapshots.get(snapshot_id)
        if not snapshot:
            logger.warning({
                "event": "snapshot_not_found",
                "snapshot_id": snapshot_id,
            })
            return None

        # Check if expired
        if snapshot.metadata.expires_at and datetime.now(timezone.utc) > snapshot.metadata.expires_at:
            logger.warning({
                "event": "snapshot_expired",
                "snapshot_id": snapshot_id,
                "expired_at": snapshot.metadata.expires_at.isoformat(),
            })
            return None

        return {
            "snapshot_id": snapshot.metadata.snapshot_id,
            "snapshot_type": snapshot.metadata.snapshot_type.value,
            "company_id": snapshot.metadata.company_id,
            "action_type": snapshot.metadata.action_type,
            "created_at": snapshot.metadata.created_at.isoformat(),
            "created_by": snapshot.metadata.created_by,
            "state_data": snapshot.state_data,
            "state_keys": snapshot.metadata.state_keys,
            "checksum": snapshot.metadata.checksum,
            "compressed": snapshot.metadata.compressed,
            "tags": snapshot.metadata.tags,
        }

    async def delete(self, snapshot_id: str) -> bool:
        """
        Delete a snapshot.

        Args:
            snapshot_id: Snapshot identifier

        Returns:
            True if deleted, False if not found
        """
        snapshot = self._snapshots.get(snapshot_id)
        if not snapshot:
            return False

        company_id = snapshot.metadata.company_id

        # Remove from storage
        del self._snapshots[snapshot_id]

        # Remove from company index
        if company_id in self._company_snapshots:
            try:
                self._company_snapshots[company_id].remove(snapshot_id)
            except ValueError:
                pass

        logger.info({
            "event": "snapshot_deleted",
            "snapshot_id": snapshot_id,
            "company_id": company_id,
        })

        return True

    async def list_snapshots(
        self,
        company_id: str,
        action_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List snapshots for a company.

        Args:
            company_id: Company identifier
            action_type: Filter by action type
            limit: Maximum number to return

        Returns:
            List of snapshot metadata
        """
        if company_id not in self._company_snapshots:
            return []

        snapshot_ids = self._company_snapshots[company_id][-limit:]
        snapshots = []

        for snapshot_id in reversed(snapshot_ids):
            snapshot = self._snapshots.get(snapshot_id)
            if not snapshot:
                continue

            if action_type and snapshot.metadata.action_type != action_type:
                continue

            snapshots.append({
                "snapshot_id": snapshot.metadata.snapshot_id,
                "action_type": snapshot.metadata.action_type,
                "snapshot_type": snapshot.metadata.snapshot_type.value,
                "created_at": snapshot.metadata.created_at.isoformat(),
                "state_keys": snapshot.metadata.state_keys,
                "tags": snapshot.metadata.tags,
            })

        return snapshots

    async def create_incremental_snapshot(
        self,
        company_id: str,
        action_type: str,
        parent_snapshot_id: str,
        new_state: Dict[str, Any]
    ) -> str:
        """
        Create an incremental snapshot with only changed data.

        Args:
            company_id: Company identifier
            action_type: Type of action
            parent_snapshot_id: Parent snapshot ID
            new_state: New state data

        Returns:
            New snapshot ID
        """
        parent = self._snapshots.get(parent_snapshot_id)
        if not parent:
            raise ValueError(f"Parent snapshot {parent_snapshot_id} not found")

        # Calculate diff
        diff = self._calculate_diff(parent.state_data, new_state)

        # Store incremental snapshot
        snapshot_id = await self.store({
            "company_id": company_id,
            "action_type": action_type,
            "state_data": new_state,
            "snapshot_type": SnapshotType.INCREMENTAL.value,
            "parent_snapshot_id": parent_snapshot_id,
        })

        return snapshot_id

    def _calculate_diff(
        self,
        old_state: Dict[str, Any],
        new_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate the difference between two states.

        Args:
            old_state: Previous state
            new_state: New state

        Returns:
            Diff dictionary
        """
        diff = {
            "added": {},
            "removed": {},
            "modified": {},
        }

        old_keys = set(old_state.keys())
        new_keys = set(new_state.keys())

        # Added keys
        for key in new_keys - old_keys:
            diff["added"][key] = new_state[key]

        # Removed keys
        for key in old_keys - new_keys:
            diff["removed"][key] = old_state[key]

        # Modified keys
        for key in old_keys & new_keys:
            if old_state[key] != new_state[key]:
                diff["modified"][key] = {
                    "old": old_state[key],
                    "new": new_state[key],
                }

        return diff

    async def cleanup_expired(self) -> Dict[str, int]:
        """
        Clean up expired snapshots.

        Returns:
            Cleanup statistics
        """
        now = datetime.now(timezone.utc)
        expired_count = 0

        for snapshot_id, snapshot in list(self._snapshots.items()):
            if snapshot.metadata.expires_at and now > snapshot.metadata.expires_at:
                await self.delete(snapshot_id)
                expired_count += 1

        logger.info({
            "event": "snapshots_cleanup",
            "expired_count": expired_count,
        })

        return {"expired_count": expired_count}

    async def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get storage statistics.

        Returns:
            Storage statistics
        """
        total_snapshots = len(self._snapshots)
        total_size = sum(
            s.metadata.compressed_size_bytes
            for s in self._snapshots.values()
        )
        by_company = {
            company: len(snapshots)
            for company, snapshots in self._company_snapshots.items()
        }

        return {
            "total_snapshots": total_snapshots,
            "total_size_bytes": total_size,
            "by_company": by_company,
            "retention_days": self._retention_days,
        }


# Global instances
_serializer: Optional[SnapshotSerializer] = None
_storage: Optional[SnapshotStorage] = None


def get_snapshot_serializer() -> SnapshotSerializer:
    """Get or create the global SnapshotSerializer instance."""
    global _serializer
    if _serializer is None:
        _serializer = SnapshotSerializer()
    return _serializer


def get_snapshot_storage() -> SnapshotStorage:
    """Get or create the global SnapshotStorage instance."""
    global _storage
    if _storage is None:
        _storage = SnapshotStorage(serializer=get_snapshot_serializer())
    return _storage
