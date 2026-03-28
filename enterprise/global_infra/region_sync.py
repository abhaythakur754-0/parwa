# Region Sync - Week 51 Builder 4
# Region synchronization

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import uuid


class SyncStatus(Enum):
    IN_SYNC = "in_sync"
    SYNCING = "syncing"
    OUT_OF_SYNC = "out_of_sync"
    CONFLICT = "conflict"


class SyncPriority(Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SyncItem:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    key: str = ""
    value: Any = None
    version: int = 1
    region: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SyncConflict:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    key: str = ""
    source_region: str = ""
    target_region: str = ""
    source_value: Any = None
    target_value: Any = None
    resolved: bool = False
    resolution: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SyncSession:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_region: str = ""
    target_region: str = ""
    status: SyncStatus = SyncStatus.SYNCING
    items_synced: int = 0
    items_total: int = 0
    conflicts: int = 0
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class RegionSync:
    """Synchronizes data between regions"""

    def __init__(self):
        self._items: Dict[str, SyncItem] = {}
        self._sessions: Dict[str, SyncSession] = {}
        self._conflicts: Dict[str, SyncConflict] = []
        self._region_state: Dict[str, Dict[str, SyncStatus]] = {}
        self._metrics = {
            "total_sessions": 0,
            "items_synced": 0,
            "conflicts_detected": 0,
            "conflicts_resolved": 0
        }

    def set_item(
        self,
        key: str,
        value: Any,
        region: str,
        version: int = 1
    ) -> SyncItem:
        """Set an item in a region"""
        item = SyncItem(
            key=key,
            value=value,
            region=region,
            version=version
        )
        self._items[f"{region}:{key}"] = item
        return item

    def get_item(self, key: str, region: str) -> Optional[SyncItem]:
        """Get an item from a region"""
        return self._items.get(f"{region}:{key}")

    def start_sync_session(
        self,
        source_region: str,
        target_region: str
    ) -> SyncSession:
        """Start a sync session"""
        session = SyncSession(
            source_region=source_region,
            target_region=target_region
        )
        self._sessions[session.id] = session
        self._metrics["total_sessions"] += 1

        # Update region state
        if source_region not in self._region_state:
            self._region_state[source_region] = {}
        self._region_state[source_region][target_region] = SyncStatus.SYNCING

        return session

    def sync_item(
        self,
        session_id: str,
        key: str,
        source_value: Any,
        target_value: Any
    ) -> bool:
        """Sync an item, detect conflicts"""
        session = self._sessions.get(session_id)
        if not session or session.status != SyncStatus.SYNCING:
            return False

        session.items_total += 1

        # Check for conflict
        if target_value is not None and source_value != target_value:
            conflict = SyncConflict(
                key=key,
                source_region=session.source_region,
                target_region=session.target_region,
                source_value=source_value,
                target_value=target_value
            )
            self._conflicts.append(conflict)
            session.conflicts += 1
            self._metrics["conflicts_detected"] += 1
            return False

        # Sync the item
        session.items_synced += 1
        self._metrics["items_synced"] += 1
        return True

    def complete_session(self, session_id: str) -> bool:
        """Complete a sync session"""
        session = self._sessions.get(session_id)
        if not session:
            return False

        session.status = SyncStatus.IN_SYNC if session.conflicts == 0 else SyncStatus.CONFLICT
        session.completed_at = datetime.utcnow()

        # Update region state
        if session.source_region in self._region_state:
            self._region_state[session.source_region][session.target_region] = session.status

        return True

    def resolve_conflict(
        self,
        conflict_id: str,
        resolution: str,
        winning_value: Any = None
    ) -> bool:
        """Resolve a sync conflict"""
        for conflict in self._conflicts:
            if conflict.id == conflict_id and not conflict.resolved:
                conflict.resolved = True
                conflict.resolution = resolution
                self._metrics["conflicts_resolved"] += 1

                # Apply winning value
                if winning_value is not None:
                    self.set_item(
                        conflict.key,
                        winning_value,
                        conflict.target_region
                    )

                return True
        return False

    def get_session(self, session_id: str) -> Optional[SyncSession]:
        """Get session by ID"""
        return self._sessions.get(session_id)

    def get_active_sessions(self) -> List[SyncSession]:
        """Get all active sessions"""
        return [s for s in self._sessions.values() if s.status == SyncStatus.SYNCING]

    def get_unresolved_conflicts(self) -> List[SyncConflict]:
        """Get all unresolved conflicts"""
        return [c for c in self._conflicts if not c.resolved]

    def get_region_status(
        self,
        source_region: str,
        target_region: str
    ) -> SyncStatus:
        """Get sync status between regions"""
        if source_region in self._region_state:
            return self._region_state[source_region].get(target_region, SyncStatus.OUT_OF_SYNC)
        return SyncStatus.OUT_OF_SYNC

    def get_last_sync_time(
        self,
        source_region: str,
        target_region: str
    ) -> Optional[datetime]:
        """Get last sync time between regions"""
        sessions = [
            s for s in self._sessions.values()
            if s.source_region == source_region
            and s.target_region == target_region
            and s.completed_at
        ]
        if sessions:
            return max(s.completed_at for s in sessions)
        return None

    def get_stale_regions(self, max_age_minutes: int = 60) -> List[Dict[str, Any]]:
        """Get regions that haven't synced recently"""
        cutoff = datetime.utcnow() - timedelta(minutes=max_age_minutes)
        stale = []

        for source, targets in self._region_state.items():
            for target, status in targets.items():
                last_sync = self.get_last_sync_time(source, target)
                if not last_sync or last_sync < cutoff:
                    stale.append({
                        "source_region": source,
                        "target_region": target,
                        "status": status.value,
                        "last_sync": last_sync.isoformat() if last_sync else None
                    })

        return stale

    def get_metrics(self) -> Dict[str, Any]:
        """Get sync metrics"""
        return {
            **self._metrics,
            "active_sessions": len(self.get_active_sessions()),
            "pending_conflicts": len(self.get_unresolved_conflicts())
        }
