"""
Incident Tracker Module - Week 53, Builder 3
Incident tracking and history
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
import logging
import json

logger = logging.getLogger(__name__)


class IncidentState(Enum):
    """Incident state for tracking"""
    CREATED = "created"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


@dataclass
class IncidentSnapshot:
    """Snapshot of incident state at a point in time"""
    incident_id: str
    state: IncidentState
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IncidentMetrics:
    """Metrics for an incident"""
    incident_id: str
    created_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    total_duration_seconds: float = 0.0
    time_to_acknowledge_seconds: float = 0.0
    time_to_resolve_seconds: float = 0.0
    event_count: int = 0


class IncidentTracker:
    """
    Tracks incident history and calculates metrics.
    """

    def __init__(self, retention_days: int = 90):
        self.retention_days = retention_days
        self.snapshots: List[IncidentSnapshot] = []
        self.metrics: Dict[str, IncidentMetrics] = {}

    def record_state(
        self,
        incident_id: str,
        state: IncidentState,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IncidentSnapshot:
        """Record incident state change"""
        snapshot = IncidentSnapshot(
            incident_id=incident_id,
            state=state,
            metadata=metadata or {},
        )
        self.snapshots.append(snapshot)
        self._prune_old_snapshots()
        return snapshot

    def start_tracking(
        self,
        incident_id: str,
        created_at: Optional[datetime] = None,
    ) -> IncidentMetrics:
        """Start tracking an incident"""
        metrics = IncidentMetrics(
            incident_id=incident_id,
            created_at=created_at or datetime.utcnow(),
        )
        self.metrics[incident_id] = metrics

        self.record_state(
            incident_id,
            IncidentState.CREATED,
            {"created_at": metrics.created_at.isoformat()},
        )

        return metrics

    def record_acknowledgement(
        self,
        incident_id: str,
        acknowledged_at: Optional[datetime] = None,
    ) -> None:
        """Record incident acknowledgement"""
        metrics = self.metrics.get(incident_id)
        if metrics:
            metrics.acknowledged_at = acknowledged_at or datetime.utcnow()
            metrics.time_to_acknowledge_seconds = (
                metrics.acknowledged_at - metrics.created_at
            ).total_seconds()

        self.record_state(incident_id, IncidentState.ACKNOWLEDGED)

    def record_resolution(
        self,
        incident_id: str,
        resolved_at: Optional[datetime] = None,
    ) -> None:
        """Record incident resolution"""
        metrics = self.metrics.get(incident_id)
        if metrics:
            metrics.resolved_at = resolved_at or datetime.utcnow()
            metrics.time_to_resolve_seconds = (
                metrics.resolved_at - metrics.created_at
            ).total_seconds()
            metrics.total_duration_seconds = metrics.time_to_resolve_seconds

        self.record_state(incident_id, IncidentState.RESOLVED)

    def get_metrics(self, incident_id: str) -> Optional[IncidentMetrics]:
        """Get metrics for an incident"""
        return self.metrics.get(incident_id)

    def get_state_history(
        self,
        incident_id: str,
    ) -> List[IncidentSnapshot]:
        """Get state history for an incident"""
        return [
            s for s in self.snapshots
            if s.incident_id == incident_id
        ]

    def calculate_mtta(self) -> float:
        """Calculate Mean Time To Acknowledge"""
        acknowledged = [
            m for m in self.metrics.values()
            if m.acknowledged_at
        ]
        if not acknowledged:
            return 0.0
        return sum(m.time_to_acknowledge_seconds for m in acknowledged) / len(acknowledged)

    def calculate_mttr(self) -> float:
        """Calculate Mean Time To Resolve"""
        resolved = [
            m for m in self.metrics.values()
            if m.resolved_at
        ]
        if not resolved:
            return 0.0
        return sum(m.time_to_resolve_seconds for m in resolved) / len(resolved)

    def get_summary(self) -> Dict[str, Any]:
        """Get tracking summary"""
        return {
            "total_tracked": len(self.metrics),
            "acknowledged": len([m for m in self.metrics.values() if m.acknowledged_at]),
            "resolved": len([m for m in self.metrics.values() if m.resolved_at]),
            "mtta_seconds": self.calculate_mtta(),
            "mttr_seconds": self.calculate_mttr(),
            "snapshots_count": len(self.snapshots),
        }

    def _prune_old_snapshots(self) -> None:
        """Remove old snapshots"""
        cutoff = datetime.utcnow() - timedelta(days=self.retention_days)
        self.snapshots = [
            s for s in self.snapshots
            if s.timestamp > cutoff
        ]

    def export_history(self) -> str:
        """Export history as JSON"""
        data = {
            "snapshots": [
                {
                    "incident_id": s.incident_id,
                    "state": s.state.value,
                    "timestamp": s.timestamp.isoformat(),
                }
                for s in self.snapshots
            ],
            "metrics": {
                k: {
                    "incident_id": v.incident_id,
                    "created_at": v.created_at.isoformat(),
                    "resolved_at": v.resolved_at.isoformat() if v.resolved_at else None,
                    "time_to_resolve_seconds": v.time_to_resolve_seconds,
                }
                for k, v in self.metrics.items()
            },
        }
        return json.dumps(data, indent=2)
