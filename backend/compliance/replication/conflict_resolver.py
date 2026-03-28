"""
Conflict Resolver for Cross-Region Replication.

Handles conflicts during replication:
- Last-write-wins strategy
- Conflict detection
- Conflict resolution logging
- Manual resolution support
- Conflict reporting
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class Region(str, Enum):
    """Available regions."""
    EU = "eu-west-1"
    US = "us-east-1"
    APAC = "ap-southeast-1"


class ConflictType(str, Enum):
    """Types of conflicts."""
    WRITE_WRITE = "write_write"
    DELETE_UPDATE = "delete_update"
    VERSION_MISMATCH = "version_mismatch"


class ResolutionStrategy(str, Enum):
    """Conflict resolution strategies."""
    LAST_WRITE_WINS = "last_write_wins"
    FIRST_WRITE_WINS = "first_write_wins"
    SOURCE_PRIORITY = "source_priority"
    MANUAL = "manual"


class ConflictStatus(str, Enum):
    """Status of a conflict."""
    DETECTED = "detected"
    RESOLVED = "resolved"
    PENDING_MANUAL = "pending_manual"


@dataclass
class ConflictRecord:
    """Record of a detected conflict."""
    conflict_id: str
    conflict_type: ConflictType
    resource_id: str
    source_region: Region
    target_region: Region
    source_data: Dict[str, Any]
    target_data: Dict[str, Any]
    source_timestamp: datetime
    target_timestamp: datetime
    status: ConflictStatus = ConflictStatus.DETECTED
    resolution: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "conflict_id": self.conflict_id,
            "conflict_type": self.conflict_type.value,
            "resource_id": self.resource_id,
            "source_region": self.source_region.value,
            "target_region": self.target_region.value,
            "status": self.status.value,
            "resolution": self.resolution,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by": self.resolved_by
        }


@dataclass
class ResolutionResult:
    """Result of conflict resolution."""
    conflict_id: str
    strategy: ResolutionStrategy
    winner_region: Region
    winning_data: Dict[str, Any]
    resolved_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "conflict_id": self.conflict_id,
            "strategy": self.strategy.value,
            "winner_region": self.winner_region.value,
            "resolved_at": self.resolved_at.isoformat()
        }


class ConflictResolver:
    """
    Resolves conflicts during replication.

    Features:
    - Last-write-wins strategy
    - Conflict detection
    - Conflict resolution logging
    - Manual resolution support
    - Conflict reporting
    """

    def __init__(
        self,
        default_strategy: ResolutionStrategy = ResolutionStrategy.LAST_WRITE_WINS,
        priority_region: Optional[Region] = None
    ):
        """
        Initialize the conflict resolver.

        Args:
            default_strategy: Default resolution strategy
            priority_region: Priority region for source_priority strategy
        """
        self.default_strategy = default_strategy
        self.priority_region = priority_region
        self._conflicts: List[ConflictRecord] = []
        self._resolutions: List[ResolutionResult] = []

    def detect_conflict(
        self,
        resource_id: str,
        source_region: Region,
        target_region: Region,
        source_data: Dict[str, Any],
        target_data: Dict[str, Any],
        source_timestamp: datetime,
        target_timestamp: datetime
    ) -> Optional[ConflictRecord]:
        """
        Detect if there's a conflict.

        Args:
            resource_id: Resource identifier
            source_region: Source region
            target_region: Target region
            source_data: Data from source
            target_data: Data from target
            source_timestamp: Timestamp of source data
            target_timestamp: Timestamp of target data

        Returns:
            ConflictRecord if conflict detected, None otherwise
        """
        # Check for version mismatch
        source_version = source_data.get("version", 0)
        target_version = target_data.get("version", 0)

        if source_version != target_version:
            conflict_type = ConflictType.VERSION_MISMATCH
        elif source_data != target_data:
            conflict_type = ConflictType.WRITE_WRITE
        else:
            # No conflict - data is identical
            return None

        conflict_id = f"conflict-{resource_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        conflict = ConflictRecord(
            conflict_id=conflict_id,
            conflict_type=conflict_type,
            resource_id=resource_id,
            source_region=source_region,
            target_region=target_region,
            source_data=source_data,
            target_data=target_data,
            source_timestamp=source_timestamp,
            target_timestamp=target_timestamp
        )

        self._conflicts.append(conflict)

        logger.warning(
            f"Conflict detected: {conflict_id} type={conflict_type.value} "
            f"resource={resource_id}"
        )

        return conflict

    def resolve(
        self,
        conflict: ConflictRecord,
        strategy: Optional[ResolutionStrategy] = None
    ) -> ResolutionResult:
        """
        Resolve a conflict.

        Args:
            conflict: Conflict to resolve
            strategy: Strategy to use (uses default if not provided)

        Returns:
            ResolutionResult with resolution details
        """
        strategy = strategy or self.default_strategy

        if strategy == ResolutionStrategy.LAST_WRITE_WINS:
            return self._resolve_last_write_wins(conflict)
        elif strategy == ResolutionStrategy.FIRST_WRITE_WINS:
            return self._resolve_first_write_wins(conflict)
        elif strategy == ResolutionStrategy.SOURCE_PRIORITY:
            return self._resolve_source_priority(conflict)
        else:
            # Manual resolution required
            conflict.status = ConflictStatus.PENDING_MANUAL
            logger.info(f"Conflict {conflict.conflict_id} requires manual resolution")
            raise ValueError("Manual resolution required")

    def _resolve_last_write_wins(self, conflict: ConflictRecord) -> ResolutionResult:
        """Resolve using last-write-wins strategy."""
        if conflict.source_timestamp > conflict.target_timestamp:
            winner_region = conflict.source_region
            winning_data = conflict.source_data
        else:
            winner_region = conflict.target_region
            winning_data = conflict.target_data

        result = ResolutionResult(
            conflict_id=conflict.conflict_id,
            strategy=ResolutionStrategy.LAST_WRITE_WINS,
            winner_region=winner_region,
            winning_data=winning_data
        )

        self._apply_resolution(conflict, result, "Last write wins")
        return result

    def _resolve_first_write_wins(self, conflict: ConflictRecord) -> ResolutionResult:
        """Resolve using first-write-wins strategy."""
        if conflict.source_timestamp < conflict.target_timestamp:
            winner_region = conflict.source_region
            winning_data = conflict.source_data
        else:
            winner_region = conflict.target_region
            winning_data = conflict.target_data

        result = ResolutionResult(
            conflict_id=conflict.conflict_id,
            strategy=ResolutionStrategy.FIRST_WRITE_WINS,
            winner_region=winner_region,
            winning_data=winning_data
        )

        self._apply_resolution(conflict, result, "First write wins")
        return result

    def _resolve_source_priority(self, conflict: ConflictRecord) -> ResolutionResult:
        """Resolve using source priority strategy."""
        if self.priority_region:
            if conflict.source_region == self.priority_region:
                winner_region = conflict.source_region
                winning_data = conflict.source_data
            elif conflict.target_region == self.priority_region:
                winner_region = conflict.target_region
                winning_data = conflict.target_data
            else:
                # Fall back to last-write-wins
                return self._resolve_last_write_wins(conflict)
        else:
            # No priority region set - use source
            winner_region = conflict.source_region
            winning_data = conflict.source_data

        result = ResolutionResult(
            conflict_id=conflict.conflict_id,
            strategy=ResolutionStrategy.SOURCE_PRIORITY,
            winner_region=winner_region,
            winning_data=winning_data
        )

        self._apply_resolution(conflict, result, "Source priority")
        return result

    def _apply_resolution(
        self,
        conflict: ConflictRecord,
        result: ResolutionResult,
        resolution: str
    ) -> None:
        """Apply resolution to conflict."""
        conflict.status = ConflictStatus.RESOLVED
        conflict.resolution = resolution
        conflict.resolved_at = datetime.now()
        self._resolutions.append(result)

        logger.info(
            f"Conflict {conflict.conflict_id} resolved: {resolution} "
            f"winner={result.winner_region.value}"
        )

    def manual_resolve(
        self,
        conflict_id: str,
        winner_region: Region,
        winning_data: Dict[str, Any],
        resolved_by: str
    ) -> ResolutionResult:
        """
        Manually resolve a conflict.

        Args:
            conflict_id: Conflict to resolve
            winner_region: Region whose data wins
            winning_data: Winning data
            resolved_by: Who resolved the conflict

        Returns:
            ResolutionResult
        """
        conflict = self._get_conflict(conflict_id)

        if not conflict:
            raise ValueError(f"Conflict {conflict_id} not found")

        result = ResolutionResult(
            conflict_id=conflict_id,
            strategy=ResolutionStrategy.MANUAL,
            winner_region=winner_region,
            winning_data=winning_data
        )

        conflict.status = ConflictStatus.RESOLVED
        conflict.resolution = "Manual resolution"
        conflict.resolved_at = datetime.now()
        conflict.resolved_by = resolved_by

        self._resolutions.append(result)

        logger.info(
            f"Conflict {conflict_id} manually resolved by {resolved_by}"
        )

        return result

    def _get_conflict(self, conflict_id: str) -> Optional[ConflictRecord]:
        """Get a conflict by ID."""
        for conflict in self._conflicts:
            if conflict.conflict_id == conflict_id:
                return conflict
        return None

    def get_conflicts(
        self,
        status: Optional[ConflictStatus] = None
    ) -> List[ConflictRecord]:
        """
        Get conflicts.

        Args:
            status: Filter by status

        Returns:
            List of conflicts
        """
        if status:
            return [c for c in self._conflicts if c.status == status]
        return self._conflicts.copy()

    def get_pending_conflicts(self) -> List[ConflictRecord]:
        """Get all conflicts pending manual resolution."""
        return [c for c in self._conflicts if c.status == ConflictStatus.PENDING_MANUAL]

    def get_stats(self) -> Dict[str, Any]:
        """Get conflict resolver statistics."""
        total = len(self._conflicts)
        resolved = len([c for c in self._conflicts if c.status == ConflictStatus.RESOLVED])
        pending = len([c for c in self._conflicts if c.status == ConflictStatus.PENDING_MANUAL])

        return {
            "total_conflicts": total,
            "resolved": resolved,
            "pending_manual": pending,
            "resolution_rate": resolved / total if total > 0 else 1.0,
            "by_type": {
                conflict_type.value: len([c for c in self._conflicts if c.conflict_type == conflict_type])
                for conflict_type in ConflictType
            }
        }


def get_conflict_resolver() -> ConflictResolver:
    """Factory function to create a conflict resolver."""
    return ConflictResolver()
