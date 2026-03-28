# Event Sourcing - Week 47 Builder 4
# Event sourcing utilities for state reconstruction

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, TypeVar, Generic
from datetime import datetime
from enum import Enum
import uuid
import json
from copy import deepcopy


T = TypeVar('T')


class EventType(Enum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    STATE_CHANGED = "state_changed"


@dataclass
class Event:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    aggregate_id: str = ""
    aggregate_type: str = ""
    event_type: str = ""
    version: int = 1
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AggregateState:
    aggregate_id: str = ""
    aggregate_type: str = ""
    version: int = 0
    state: Dict[str, Any] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.utcnow)


class EventStore:
    """Stores events for event sourcing"""

    def __init__(self):
        self._events: Dict[str, List[Event]] = {}
        self._all_events: List[Event] = []

    async def append(self, event: Event) -> None:
        """Append an event to the store"""
        if event.aggregate_id not in self._events:
            self._events[event.aggregate_id] = []
        self._events[event.aggregate_id].append(event)
        self._all_events.append(event)

    async def get_events(
        self,
        aggregate_id: str,
        from_version: int = 0
    ) -> List[Event]:
        """Get events for an aggregate"""
        events = self._events.get(aggregate_id, [])
        return [e for e in events if e.version > from_version]

    async def get_all_events(
        self,
        from_timestamp: Optional[datetime] = None
    ) -> List[Event]:
        """Get all events from a timestamp"""
        if from_timestamp is None:
            return self._all_events.copy()
        return [e for e in self._all_events if e.created_at >= from_timestamp]


class AggregateRoot(Generic[T]):
    """Base class for aggregate roots"""

    def __init__(self, aggregate_id: str):
        self.aggregate_id = aggregate_id
        self.version = 0
        self._uncommitted_events: List[Event] = []
        self._state: Dict[str, Any] = {}

    def apply_event(self, event: Event) -> None:
        """Apply an event to update state"""
        self.version = event.version
        self._state = self._apply(event)

    def _apply(self, event: Event) -> Dict[str, Any]:
        """Override to implement event application logic"""
        return self._state

    def raise_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Event:
        """Raise a new event"""
        self.version += 1
        event = Event(
            aggregate_id=self.aggregate_id,
            aggregate_type=self.__class__.__name__,
            event_type=event_type,
            version=self.version,
            data=data,
            metadata=metadata or {}
        )
        self._uncommitted_events.append(event)
        self.apply_event(event)
        return event

    def get_uncommitted_events(self) -> List[Event]:
        """Get uncommitted events"""
        return self._uncommitted_events.copy()

    def mark_events_committed(self) -> None:
        """Mark all events as committed"""
        self._uncommitted_events.clear()


class EventSourcingRepository(Generic[T]):
    """Repository for event-sourced aggregates"""

    def __init__(self, event_store: EventStore):
        self._event_store = event_store
        self._aggregate_factories: Dict[str, Callable] = {}

    def register_aggregate_type(
        self,
        aggregate_type: str,
        factory: Callable[[str], AggregateRoot]
    ) -> None:
        """Register a factory for an aggregate type"""
        self._aggregate_factories[aggregate_type] = factory

    async def save(self, aggregate: AggregateRoot) -> None:
        """Save an aggregate's uncommitted events"""
        events = aggregate.get_uncommitted_events()
        for event in events:
            await self._event_store.append(event)
        aggregate.mark_events_committed()

    async def get_by_id(
        self,
        aggregate_id: str,
        aggregate_type: str
    ) -> Optional[AggregateRoot]:
        """Reconstruct an aggregate from events"""
        factory = self._aggregate_factories.get(aggregate_type)
        if not factory:
            return None

        aggregate = factory(aggregate_id)
        events = await self._event_store.get_events(aggregate_id)

        if not events:
            return None

        for event in events:
            aggregate.apply_event(event)

        return aggregate

    async def get_state_at_version(
        self,
        aggregate_id: str,
        aggregate_type: str,
        target_version: int
    ) -> Optional[Dict[str, Any]]:
        """Get aggregate state at a specific version"""
        factory = self._aggregate_factories.get(aggregate_type)
        if not factory:
            return None

        aggregate = factory(aggregate_id)
        events = await self._event_store.get_events(aggregate_id)

        for event in events:
            if event.version > target_version:
                break
            aggregate.apply_event(event)

        return aggregate._state


class StateReconstructor:
    """Reconstructs state from events"""

    def __init__(self, event_store: EventStore):
        self._event_store = event_store
        self._appliers: Dict[str, Callable[[Dict, Event], Dict]] = {}

    def register_applier(
        self,
        event_type: str,
        applier: Callable[[Dict, Event], Dict]
    ) -> None:
        """Register a state applier for an event type"""
        self._appliers[event_type] = applier

    async def reconstruct(
        self,
        aggregate_id: str,
        initial_state: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Reconstruct state from all events"""
        state = initial_state or {}
        events = await self._event_store.get_events(aggregate_id)

        for event in events:
            state = self._apply_event(state, event)

        return state

    async def reconstruct_at_time(
        self,
        aggregate_id: str,
        target_time: datetime,
        initial_state: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Reconstruct state at a specific point in time"""
        state = initial_state or {}
        events = await self._event_store.get_events(aggregate_id)

        for event in events:
            if event.created_at > target_time:
                break
            state = self._apply_event(state, event)

        return state

    def _apply_event(
        self,
        state: Dict[str, Any],
        event: Event
    ) -> Dict[str, Any]:
        """Apply an event to state"""
        applier = self._appliers.get(event.event_type)
        if applier:
            return applier(state, event)
        return state


class Snapshot:
    """Snapshot for optimization"""

    def __init__(
        self,
        aggregate_id: str,
        aggregate_type: str,
        version: int,
        state: Dict[str, Any],
        timestamp: datetime
    ):
        self.aggregate_id = aggregate_id
        self.aggregate_type = aggregate_type
        self.version = version
        self.state = state
        self.timestamp = timestamp


class SnapshotStore:
    """Stores snapshots for fast state reconstruction"""

    def __init__(self, event_store: EventStore):
        self._event_store = event_store
        self._snapshots: Dict[str, Snapshot] = {}
        self._snapshot_interval = 100

    async def get_snapshot(self, aggregate_id: str) -> Optional[Snapshot]:
        """Get the latest snapshot for an aggregate"""
        return self._snapshots.get(aggregate_id)

    async def save_snapshot(
        self,
        aggregate_id: str,
        aggregate_type: str,
        version: int,
        state: Dict[str, Any]
    ) -> Snapshot:
        """Save a snapshot"""
        snapshot = Snapshot(
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
            version=version,
            state=deepcopy(state),
            timestamp=datetime.utcnow()
        )
        self._snapshots[aggregate_id] = snapshot
        return snapshot

    async def should_create_snapshot(
        self,
        aggregate_id: str,
        current_version: int
    ) -> bool:
        """Check if a new snapshot should be created"""
        snapshot = await self.get_snapshot(aggregate_id)
        if not snapshot:
            return current_version >= self._snapshot_interval
        return (current_version - snapshot.version) >= self._snapshot_interval

    async def reconstruct_with_snapshot(
        self,
        aggregate_id: str,
        reconstructor: StateReconstructor
    ) -> Dict[str, Any]:
        """Reconstruct state using snapshot + remaining events"""
        snapshot = await self.get_snapshot(aggregate_id)

        if snapshot:
            state = deepcopy(snapshot.state)
            events = await self._event_store.get_events(
                aggregate_id,
                from_version=snapshot.version
            )
        else:
            state = {}
            events = await self._event_store.get_events(aggregate_id)

        for event in events:
            state = reconstructor._apply_event(state, event)

        return state
