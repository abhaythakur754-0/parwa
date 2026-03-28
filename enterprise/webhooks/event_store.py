"""Event Store - Persistent Event Storage"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import logging
import json
from collections import defaultdict

logger = logging.getLogger(__name__)

@dataclass
class StoredEvent:
    event_id: str
    event_type: str
    tenant_id: str
    data: Dict[str, Any]
    timestamp: datetime
    sequence_number: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    replay_count: int = 0

class EventStore:
    def __init__(self, max_events: int = 100000):
        self.max_events = max_events
        self._events: List[StoredEvent] = []
        self._events_by_id: Dict[str, StoredEvent] = {}
        self._events_by_tenant: Dict[str, List[str]] = defaultdict(list)
        self._events_by_type: Dict[str, List[str]] = defaultdict(list)
        self._sequence = 0

    def store(self, event_id: str, event_type: str, tenant_id: str, data: Dict[str, Any], metadata: Dict[str, Any] = None) -> StoredEvent:
        self._sequence += 1
        event = StoredEvent(
            event_id=event_id,
            event_type=event_type,
            tenant_id=tenant_id,
            data=data,
            timestamp=datetime.utcnow(),
            sequence_number=self._sequence,
            metadata=metadata or {}
        )

        self._events.append(event)
        self._events_by_id[event_id] = event
        self._events_by_tenant[tenant_id].append(event_id)
        self._events_by_type[event_type].append(event_id)

        if len(self._events) > self.max_events:
            self._evict_oldest()

        return event

    def _evict_oldest(self) -> None:
        oldest = self._events.pop(0)
        if oldest.event_id in self._events_by_id:
            del self._events_by_id[oldest.event_id]
        if oldest.tenant_id in self._events_by_tenant:
            self._events_by_tenant[oldest.tenant_id] = [eid for eid in self._events_by_tenant[oldest.tenant_id] if eid != oldest.event_id]
        if oldest.event_type in self._events_by_type:
            self._events_by_type[oldest.event_type] = [eid for eid in self._events_by_type[oldest.event_type] if eid != oldest.event_id]

    def get(self, event_id: str) -> Optional[StoredEvent]:
        return self._events_by_id.get(event_id)

    def get_by_tenant(self, tenant_id: str, limit: int = 100, offset: int = 0) -> List[StoredEvent]:
        event_ids = self._events_by_tenant.get(tenant_id, [])
        return [self._events_by_id[eid] for eid in event_ids[offset:offset + limit] if eid in self._events_by_id]

    def get_by_type(self, event_type: str, limit: int = 100) -> List[StoredEvent]:
        event_ids = self._events_by_type.get(event_type, [])
        return [self._events_by_id[eid] for eid in event_ids[-limit:] if eid in self._events_by_id]

    def get_by_time_range(self, start: datetime, end: datetime) -> List[StoredEvent]:
        return [e for e in self._events if start <= e.timestamp <= end]

    def get_since_sequence(self, sequence: int, limit: int = 100) -> List[StoredEvent]:
        return [e for e in self._events if e.sequence_number > sequence][:limit]

    def replay_events(self, tenant_id: str, callback: callable, event_types: List[str] = None) -> int:
        event_ids = self._events_by_tenant.get(tenant_id, [])
        replayed = 0
        for eid in event_ids:
            event = self._events_by_id.get(eid)
            if event and (not event_types or event.event_type in event_types):
                event.replay_count += 1
                callback(event)
                replayed += 1
        return replayed

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "total_events": len(self._events),
            "total_tenants": len(self._events_by_tenant),
            "total_event_types": len(self._events_by_type),
            "sequence_number": self._sequence,
            "events_by_type": {k: len(v) for k, v in self._events_by_type.items()}
        }

    def clear_tenant_events(self, tenant_id: str) -> int:
        event_ids = self._events_by_tenant.get(tenant_id, [])
        for eid in event_ids:
            if eid in self._events_by_id:
                del self._events_by_id[eid]
        del self._events_by_tenant[tenant_id]
        self._events = [e for e in self._events if e.tenant_id != tenant_id]
        return len(event_ids)
