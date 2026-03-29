"""Event Handler Module - Week 57, Builder 3"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import logging
import threading
import uuid

logger = logging.getLogger(__name__)


class EventType(Enum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    CUSTOM = "custom"
    SYSTEM = "system"


@dataclass
class Event:
    event_type: EventType
    source: str
    payload: Dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, handler: Callable) -> None:
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable) -> bool:
        with self._lock:
            if event_type in self._subscribers and handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)
                return True
            return False

    def publish(self, event: Event) -> int:
        handlers = self._subscribers.get(event.event_type.value, [])
        handled = 0
        for handler in handlers:
            try:
                handler(event)
                handled += 1
            except Exception as e:
                logger.error(f"Handler error: {e}")
        return handled

    def publish_async(self, event: Event) -> None:
        import threading
        threading.Thread(target=self.publish, args=(event,)).start()


class EventStore:
    def __init__(self, max_events: int = 10000):
        self.max_events = max_events
        self._events: List[Event] = []
        self._lock = threading.Lock()

    def append(self, event: Event) -> None:
        with self._lock:
            self._events.append(event)
            if len(self._events) > self.max_events:
                self._events = self._events[-self.max_events:]

    def get_events(self, event_type: Optional[EventType] = None, limit: int = 100) -> List[Event]:
        with self._lock:
            events = self._events
            if event_type:
                events = [e for e in events if e.event_type == event_type]
            return events[-limit:]

    def get_by_source(self, source: str) -> List[Event]:
        with self._lock:
            return [e for e in self._events if e.source == source]

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


class EventHandler:
    def __init__(self, bus: EventBus, store: EventStore = None):
        self.bus = bus
        self.store = store or EventStore()

    def on(self, event_type: str, handler: Callable) -> None:
        def wrapped(event: Event):
            result = handler(event)
            self.store.append(event)
            return result
        self.bus.subscribe(event_type, wrapped)

    def emit(self, event_type: EventType, source: str, payload: Dict = None) -> Event:
        event = Event(
            event_type=event_type,
            source=source,
            payload=payload or {}
        )
        self.bus.publish(event)
        self.store.append(event)
        return event

    def get_history(self, limit: int = 100) -> List[Event]:
        return self.store.get_events(limit=limit)
