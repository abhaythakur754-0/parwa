# Audit Trail - Week 49 Builder 1
# Audit trail management and tracking

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
import uuid


class TrailStatus(Enum):
    ACTIVE = "active"
    CLOSED = "closed"
    ARCHIVED = "archived"


@dataclass
class AuditTrailEntry:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trail_id: str = ""
    sequence_number: int = 0
    event_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    checksum: str = ""
    previous_checksum: str = ""


@dataclass
class AuditTrail:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    name: str = ""
    description: str = ""
    status: TrailStatus = TrailStatus.ACTIVE
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    entries: List[AuditTrailEntry] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    last_entry_at: Optional[datetime] = None


class AuditTrailManager:
    """Manages audit trails for compliance tracking"""

    def __init__(self):
        self._trails: Dict[str, AuditTrail] = {}
        self._tenant_trails: Dict[str, List[str]] = {}
        self._checksum_chain: Dict[str, str] = {}
        self._metrics = {
            "total_trails": 0,
            "total_entries": 0,
            "active_trails": 0
        }

    def create_trail(
        self,
        tenant_id: str,
        name: str,
        description: str = "",
        created_by: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> AuditTrail:
        """Create a new audit trail"""
        trail = AuditTrail(
            tenant_id=tenant_id,
            name=name,
            description=description,
            created_by=created_by,
            metadata=metadata or {}
        )

        self._trails[trail.id] = trail

        if tenant_id not in self._tenant_trails:
            self._tenant_trails[tenant_id] = []
        self._tenant_trails[tenant_id].append(trail.id)

        self._metrics["total_trails"] += 1
        self._metrics["active_trails"] += 1

        return trail

    def add_entry(
        self,
        trail_id: str,
        event_id: str,
        event_data: Optional[Dict[str, Any]] = None
    ) -> Optional[AuditTrailEntry]:
        """Add an entry to an audit trail"""
        trail = self._trails.get(trail_id)
        if not trail or trail.status != TrailStatus.ACTIVE:
            return None

        # Calculate checksum for integrity
        import hashlib
        import json

        previous_checksum = ""
        if trail.entries:
            previous_checksum = trail.entries[-1].checksum

        # Use the same timestamp for both entry and checksum
        now = datetime.utcnow()
        entry_data = {
            "event_id": event_id,
            "timestamp": now.isoformat(),
            "previous_checksum": previous_checksum
        }
        checksum = hashlib.sha256(
            json.dumps(entry_data, sort_keys=True).encode()
        ).hexdigest()

        entry = AuditTrailEntry(
            trail_id=trail_id,
            sequence_number=len(trail.entries) + 1,
            event_id=event_id,
            timestamp=now,
            checksum=checksum,
            previous_checksum=previous_checksum
        )

        trail.entries.append(entry)
        trail.last_entry_at = datetime.utcnow()
        self._metrics["total_entries"] += 1

        return entry

    def close_trail(self, trail_id: str) -> bool:
        """Close an audit trail"""
        trail = self._trails.get(trail_id)
        if not trail or trail.status != TrailStatus.ACTIVE:
            return False

        trail.status = TrailStatus.CLOSED
        trail.end_time = datetime.utcnow()
        self._metrics["active_trails"] -= 1

        return True

    def archive_trail(self, trail_id: str) -> bool:
        """Archive a closed trail"""
        trail = self._trails.get(trail_id)
        if not trail or trail.status != TrailStatus.CLOSED:
            return False

        trail.status = TrailStatus.ARCHIVED
        return True

    def get_trail(self, trail_id: str) -> Optional[AuditTrail]:
        """Get a trail by ID"""
        return self._trails.get(trail_id)

    def get_tenant_trails(
        self,
        tenant_id: str,
        status: Optional[TrailStatus] = None
    ) -> List[AuditTrail]:
        """Get all trails for a tenant"""
        trail_ids = self._tenant_trails.get(tenant_id, [])
        trails = [self._trails[tid] for tid in trail_ids if tid in self._trails]

        if status:
            trails = [t for t in trails if t.status == status]

        return trails

    def verify_trail_integrity(self, trail_id: str) -> Dict[str, Any]:
        """Verify the integrity of a trail's checksum chain"""
        trail = self._trails.get(trail_id)
        if not trail:
            return {"valid": False, "error": "Trail not found"}

        import hashlib
        import json

        for i, entry in enumerate(trail.entries):
            # Verify checksum chain
            expected_previous = ""
            if i > 0:
                expected_previous = trail.entries[i - 1].checksum

            if entry.previous_checksum != expected_previous:
                return {
                    "valid": False,
                    "error": f"Checksum chain broken at entry {i}",
                    "entry_id": entry.id
                }

            # Verify checksum calculation
            entry_data = {
                "event_id": entry.event_id,
                "timestamp": entry.timestamp.isoformat(),
                "previous_checksum": entry.previous_checksum
            }
            expected_checksum = hashlib.sha256(
                json.dumps(entry_data, sort_keys=True).encode()
            ).hexdigest()

            if entry.checksum != expected_checksum:
                return {
                    "valid": False,
                    "error": f"Invalid checksum at entry {i}",
                    "entry_id": entry.id
                }

        return {"valid": True, "entries_verified": len(trail.entries)}

    def get_trail_timeline(
        self,
        trail_id: str
    ) -> List[Dict[str, Any]]:
        """Get chronological timeline of trail entries"""
        trail = self._trails.get(trail_id)
        if not trail:
            return []

        return [
            {
                "sequence": entry.sequence_number,
                "event_id": entry.event_id,
                "timestamp": entry.timestamp.isoformat(),
                "checksum": entry.checksum[:16] + "..."  # Truncated for display
            }
            for entry in trail.entries
        ]

    def get_entry_count(self, trail_id: str) -> int:
        """Get number of entries in a trail"""
        trail = self._trails.get(trail_id)
        return len(trail.entries) if trail else 0

    def get_metrics(self) -> Dict[str, Any]:
        """Get trail manager metrics"""
        return {
            **self._metrics,
            "trails_by_status": {
                "active": len([t for t in self._trails.values() if t.status == TrailStatus.ACTIVE]),
                "closed": len([t for t in self._trails.values() if t.status == TrailStatus.CLOSED]),
                "archived": len([t for t in self._trails.values() if t.status == TrailStatus.ARCHIVED])
            }
        }

    def search_entries(
        self,
        tenant_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AuditTrailEntry]:
        """Search entries across tenant's trails"""
        trails = self.get_tenant_trails(tenant_id)
        entries = []

        for trail in trails:
            for entry in trail.entries:
                if start_time and entry.timestamp < start_time:
                    continue
                if end_time and entry.timestamp > end_time:
                    continue
                entries.append(entry)

        # Sort by timestamp
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries[:limit]

    def export_trail(
        self,
        trail_id: str,
        format: str = "json"
    ) -> Optional[Dict[str, Any]]:
        """Export trail for compliance"""
        trail = self._trails.get(trail_id)
        if not trail:
            return None

        return {
            "trail_id": trail.id,
            "tenant_id": trail.tenant_id,
            "name": trail.name,
            "description": trail.description,
            "status": trail.status.value,
            "start_time": trail.start_time.isoformat(),
            "end_time": trail.end_time.isoformat() if trail.end_time else None,
            "entries": [
                {
                    "sequence": e.sequence_number,
                    "event_id": e.event_id,
                    "timestamp": e.timestamp.isoformat(),
                    "checksum": e.checksum
                }
                for e in trail.entries
            ],
            "exported_at": datetime.utcnow().isoformat(),
            "entry_count": len(trail.entries)
        }

    def delete_trail(self, trail_id: str) -> bool:
        """Delete an archived trail"""
        trail = self._trails.get(trail_id)
        if not trail or trail.status != TrailStatus.ARCHIVED:
            return False

        # Remove from tenant's trail list
        if trail.tenant_id in self._tenant_trails:
            self._tenant_trails[trail.tenant_id] = [
                tid for tid in self._tenant_trails[trail.tenant_id]
                if tid != trail_id
            ]

        del self._trails[trail_id]
        self._metrics["total_trails"] -= 1

        return True
