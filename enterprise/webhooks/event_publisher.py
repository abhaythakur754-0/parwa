# Event Publisher - Week 47 Builder 2
# Event publishing system for webhook events

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
import asyncio
import uuid
import json


class PublishStatus(Enum):
    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"


@dataclass
class PublishedEvent:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    topic: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: PublishStatus = PublishStatus.PENDING
    subscriber_count: int = 0
    delivery_count: int = 0
    published_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


class EventPublisher:
    """Publishes events to the event bus and notifies subscribers"""

    def __init__(self, event_bus=None):
        self._event_bus = event_bus
        self._published_events: Dict[str, PublishedEvent] = {}
        self._middlewares: List[Callable] = []
        self._metrics = {
            "total_published": 0,
            "total_failed": 0,
            "by_topic": {},
            "by_type": {}
        }

    def set_event_bus(self, event_bus) -> None:
        """Set the event bus instance"""
        self._event_bus = event_bus

    def add_middleware(self, middleware: Callable) -> None:
        """Add middleware for event processing"""
        self._middlewares.append(middleware)

    async def _apply_middlewares(self, event: PublishedEvent) -> PublishedEvent:
        """Apply all middlewares to the event"""
        for middleware in self._middlewares:
            if asyncio.iscoroutinefunction(middleware):
                event = await middleware(event)
            else:
                event = middleware(event)
        return event

    async def publish(
        self,
        event_type: str,
        topic: str,
        payload: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> PublishedEvent:
        """Publish an event to the event bus"""
        event = PublishedEvent(
            event_type=event_type,
            topic=topic,
            payload=payload,
            metadata=metadata or {}
        )

        # Apply middlewares
        event = await self._apply_middlewares(event)

        # Publish to event bus if available
        if self._event_bus:
            try:
                result = await self._event_bus.publish(
                    event_type=event_type,
                    payload=payload,
                    topic=topic
                )
                event.status = PublishStatus.PUBLISHED
                event.published_at = datetime.utcnow()
                event.subscriber_count = result.get("subscriber_count", 0)
                event.delivery_count = result.get("delivery_count", 0)
                self._metrics["total_published"] += 1
            except Exception as e:
                event.status = PublishStatus.FAILED
                self._metrics["total_failed"] += 1
        else:
            event.status = PublishStatus.PUBLISHED
            event.published_at = datetime.utcnow()
            self._metrics["total_published"] += 1

        # Update topic/type metrics
        if topic not in self._metrics["by_topic"]:
            self._metrics["by_topic"][topic] = 0
        self._metrics["by_topic"][topic] += 1

        if event_type not in self._metrics["by_type"]:
            self._metrics["by_type"][event_type] = 0
        self._metrics["by_type"][event_type] += 1

        self._published_events[event.id] = event
        return event

    async def publish_batch(
        self,
        events: List[Dict[str, Any]]
    ) -> List[PublishedEvent]:
        """Publish multiple events at once"""
        results = []
        for event_data in events:
            result = await self.publish(
                event_type=event_data.get("event_type", "generic"),
                topic=event_data.get("topic", "default"),
                payload=event_data.get("payload", {}),
                metadata=event_data.get("metadata")
            )
            results.append(result)
        return results

    async def publish_with_delay(
        self,
        event_type: str,
        topic: str,
        payload: Dict[str, Any],
        delay_seconds: int
    ) -> PublishedEvent:
        """Publish an event after a delay"""
        await asyncio.sleep(delay_seconds)
        return await self.publish(event_type, topic, payload)

    def get_event(self, event_id: str) -> Optional[PublishedEvent]:
        """Get a published event by ID"""
        return self._published_events.get(event_id)

    def get_events_by_topic(self, topic: str) -> List[PublishedEvent]:
        """Get all events for a topic"""
        return [e for e in self._published_events.values() if e.topic == topic]

    def get_events_by_type(self, event_type: str) -> List[PublishedEvent]:
        """Get all events of a specific type"""
        return [e for e in self._published_events.values() if e.event_type == event_type]

    def get_failed_events(self) -> List[PublishedEvent]:
        """Get all failed events"""
        return [e for e in self._published_events.values() 
                if e.status == PublishStatus.FAILED]

    async def retry_failed(self, event_id: str) -> PublishedEvent:
        """Retry a failed event"""
        event = self._published_events.get(event_id)
        if not event or event.status != PublishStatus.FAILED:
            return event

        return await self.publish(
            event_type=event.event_type,
            topic=event.topic,
            payload=event.payload,
            metadata=event.metadata
        )

    def get_metrics(self) -> Dict[str, Any]:
        """Get publisher metrics"""
        return {
            **self._metrics,
            "total_events": len(self._published_events)
        }

    def clear_history(self, older_than: Optional[datetime] = None) -> int:
        """Clear published event history"""
        if older_than is None:
            count = len(self._published_events)
            self._published_events.clear()
            return count

        to_remove = [
            eid for eid, e in self._published_events.items()
            if e.created_at < older_than
        ]
        for eid in to_remove:
            del self._published_events[eid]
        return len(to_remove)
