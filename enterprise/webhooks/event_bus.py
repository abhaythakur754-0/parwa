"""Event Bus - Central Event Distribution"""
from typing import Dict, List, Optional, Any, Callable, Set
from datetime import datetime
from dataclasses import dataclass, field
import logging
import asyncio
import uuid

logger = logging.getLogger(__name__)

@dataclass
class Event:
    event_id: str
    event_type: str
    tenant_id: str
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: str = "system"

class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._async_subscribers: Dict[str, List[Callable]] = {}
        self._event_history: List[Event] = []
        self._max_history = 10000
        self._metrics = {"events_published": 0, "events_delivered": 0, "delivery_errors": 0}

    def subscribe(self, event_type: str, handler: Callable) -> str:
        subscription_id = str(uuid.uuid4())
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        logger.info(f"Subscribed to event type: {event_type}")
        return subscription_id

    def subscribe_async(self, event_type: str, handler: Callable) -> str:
        subscription_id = str(uuid.uuid4())
        if event_type not in self._async_subscribers:
            self._async_subscribers[event_type] = []
        self._async_subscribers[event_type].append(handler)
        return subscription_id

    def unsubscribe(self, subscription_id: str) -> bool:
        for event_type, handlers in list(self._subscribers.items()):
            for i, handler in enumerate(handlers):
                if getattr(handler, '_subscription_id', None) == subscription_id:
                    del handlers[i]
                    return True
        return False

    def publish(self, event_type: str, tenant_id: str, data: Dict[str, Any], source: str = "system") -> Event:
        event = Event(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            event_type=event_type,
            tenant_id=tenant_id,
            data=data,
            source=source
        )
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)

        self._metrics["events_published"] += 1
        self._deliver(event)
        return event

    async def publish_async(self, event_type: str, tenant_id: str, data: Dict[str, Any], source: str = "system") -> Event:
        event = Event(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            event_type=event_type,
            tenant_id=tenant_id,
            data=data,
            source=source
        )
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)

        self._metrics["events_published"] += 1
        await self._deliver_async(event)
        return event

    def _deliver(self, event: Event) -> None:
        handlers = self._subscribers.get(event.event_type, []) + self._subscribers.get("*", [])
        for handler in handlers:
            try:
                handler(event)
                self._metrics["events_delivered"] += 1
            except Exception as e:
                self._metrics["delivery_errors"] += 1
                logger.error(f"Event delivery error: {e}")

    async def _deliver_async(self, event: Event) -> None:
        handlers = self._async_subscribers.get(event.event_type, []) + self._async_subscribers.get("*", [])
        for handler in handlers:
            try:
                await handler(event)
                self._metrics["events_delivered"] += 1
            except Exception as e:
                self._metrics["delivery_errors"] += 1
                logger.error(f"Async event delivery error: {e}")

    def get_event(self, event_id: str) -> Optional[Event]:
        for event in self._event_history:
            if event.event_id == event_id:
                return event
        return None

    def get_events_by_type(self, event_type: str, limit: int = 100) -> List[Event]:
        events = [e for e in self._event_history if e.event_type == event_type]
        return events[-limit:]

    def get_events_by_tenant(self, tenant_id: str, limit: int = 100) -> List[Event]:
        events = [e for e in self._event_history if e.tenant_id == tenant_id]
        return events[-limit:]

    def get_metrics(self) -> Dict[str, Any]:
        return {**self._metrics, "history_size": len(self._event_history), "subscriber_count": sum(len(h) for h in self._subscribers.values())}

    def clear_history(self) -> int:
        count = len(self._event_history)
        self._event_history.clear()
        return count
