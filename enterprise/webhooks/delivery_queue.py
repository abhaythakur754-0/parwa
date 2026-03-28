# Delivery Queue - Week 47 Builder 3
# Queue management for webhook deliveries

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import heapq
import uuid


class DeliveryPriority(Enum):
    LOW = 1
    NORMAL = 5
    HIGH = 10
    URGENT = 20


class DeliveryStatus(Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class DeliveryItem:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    webhook_id: str = ""
    tenant_id: str = ""
    url: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    priority: DeliveryPriority = DeliveryPriority.NORMAL
    status: DeliveryStatus = DeliveryStatus.QUEUED
    retry_count: int = 0
    max_retries: int = 3
    scheduled_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __lt__(self, other):
        # Higher priority = processed first
        return self.priority.value > other.priority.value


class DeliveryQueue:
    """Priority queue for webhook deliveries"""

    def __init__(self):
        self._queue: List[DeliveryItem] = []
        self._items: Dict[str, DeliveryItem] = {}
        self._lock = asyncio.Lock()
        self._processors: List[Callable] = []
        self._metrics = {
            "total_queued": 0,
            "total_processed": 0,
            "total_failed": 0,
            "by_priority": {p.name: 0 for p in DeliveryPriority}
        }

    def register_processor(self, processor: Callable) -> None:
        """Register a delivery processor"""
        self._processors.append(processor)

    async def enqueue(
        self,
        webhook_id: str,
        tenant_id: str,
        url: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        priority: DeliveryPriority = DeliveryPriority.NORMAL,
        scheduled_at: Optional[datetime] = None
    ) -> DeliveryItem:
        """Add an item to the delivery queue"""
        item = DeliveryItem(
            webhook_id=webhook_id,
            tenant_id=tenant_id,
            url=url,
            payload=payload,
            headers=headers or {},
            priority=priority,
            scheduled_at=scheduled_at
        )

        async with self._lock:
            heapq.heappush(self._queue, item)
            self._items[item.id] = item
            self._metrics["total_queued"] += 1
            self._metrics["by_priority"][priority.name] += 1

        return item

    async def enqueue_batch(
        self,
        items: List[Dict[str, Any]]
    ) -> List[DeliveryItem]:
        """Add multiple items to the queue"""
        results = []
        for item_data in items:
            item = await self.enqueue(
                webhook_id=item_data.get("webhook_id", ""),
                tenant_id=item_data.get("tenant_id", ""),
                url=item_data.get("url", ""),
                payload=item_data.get("payload", {}),
                headers=item_data.get("headers"),
                priority=item_data.get("priority", DeliveryPriority.NORMAL),
                scheduled_at=item_data.get("scheduled_at")
            )
            results.append(item)
        return results

    async def dequeue(self) -> Optional[DeliveryItem]:
        """Get the next item from the queue"""
        async with self._lock:
            while self._queue:
                item = heapq.heappop(self._queue)
                
                # Skip items scheduled for future
                if item.scheduled_at and item.scheduled_at > datetime.utcnow():
                    heapq.heappush(self._queue, item)
                    return None
                
                item.status = DeliveryStatus.PROCESSING
                return item
            return None

    async def peek(self) -> Optional[DeliveryItem]:
        """Peek at the next item without removing it"""
        async with self._lock:
            return self._queue[0] if self._queue else None

    async def size(self) -> int:
        """Get queue size"""
        async with self._lock:
            return len(self._queue)

    async def is_empty(self) -> bool:
        """Check if queue is empty"""
        async with self._lock:
            return len(self._queue) == 0

    async def mark_delivered(self, item_id: str) -> bool:
        """Mark an item as delivered"""
        item = self._items.get(item_id)
        if not item:
            return False
        item.status = DeliveryStatus.DELIVERED
        item.processed_at = datetime.utcnow()
        self._metrics["total_processed"] += 1
        return True

    async def mark_failed(
        self,
        item_id: str,
        retry: bool = True
    ) -> bool:
        """Mark an item as failed and optionally requeue"""
        item = self._items.get(item_id)
        if not item:
            return False

        if retry and item.retry_count < item.max_retries:
            item.retry_count += 1
            item.status = DeliveryStatus.RETRYING
            async with self._lock:
                heapq.heappush(self._queue, item)
        else:
            item.status = DeliveryStatus.FAILED
            item.processed_at = datetime.utcnow()
            self._metrics["total_failed"] += 1

        return True

    async def requeue(self, item_id: str) -> bool:
        """Requeue an item for retry"""
        item = self._items.get(item_id)
        if not item:
            return False

        item.status = DeliveryStatus.QUEUED
        async with self._lock:
            heapq.heappush(self._queue, item)
        return True

    async def cancel(self, item_id: str) -> bool:
        """Cancel a queued item"""
        async with self._lock:
            item = self._items.get(item_id)
            if not item or item.status != DeliveryStatus.QUEUED:
                return False
            item.status = DeliveryStatus.FAILED
            return True

    def get_item(self, item_id: str) -> Optional[DeliveryItem]:
        """Get an item by ID"""
        return self._items.get(item_id)

    def get_items_by_webhook(self, webhook_id: str) -> List[DeliveryItem]:
        """Get all items for a webhook"""
        return [i for i in self._items.values() if i.webhook_id == webhook_id]

    def get_items_by_tenant(self, tenant_id: str) -> List[DeliveryItem]:
        """Get all items for a tenant"""
        return [i for i in self._items.values() if i.tenant_id == tenant_id]

    async def process_batch(
        self,
        batch_size: int = 10
    ) -> List[DeliveryItem]:
        """Process a batch of items"""
        processed = []
        for _ in range(batch_size):
            item = await self.dequeue()
            if item is None:
                break

            for processor in self._processors:
                try:
                    if asyncio.iscoroutinefunction(processor):
                        success = await processor(item)
                    else:
                        success = processor(item)

                    if success:
                        await self.mark_delivered(item.id)
                    else:
                        await self.mark_failed(item.id)
                except Exception:
                    await self.mark_failed(item.id)

            processed.append(item)

        return processed

    async def clear(self) -> int:
        """Clear the queue"""
        async with self._lock:
            count = len(self._queue)
            self._queue.clear()
            return count

    def get_metrics(self) -> Dict[str, Any]:
        """Get queue metrics"""
        status_counts = {s.value: 0 for s in DeliveryStatus}
        for item in self._items.values():
            status_counts[item.status.value] += 1

        return {
            **self._metrics,
            "queue_size": asyncio.get_event_loop().run_until_complete(self.size()) 
                        if asyncio.get_event_loop().is_running() else 0,
            "total_items": len(self._items),
            "status_counts": status_counts
        }

    def get_retry_items(self) -> List[DeliveryItem]:
        """Get all items that are retrying"""
        return [i for i in self._items.values() if i.status == DeliveryStatus.RETRYING]

    def get_failed_items(self) -> List[DeliveryItem]:
        """Get all failed items"""
        return [i for i in self._items.values() if i.status == DeliveryStatus.FAILED]

    async def purge_old_items(
        self,
        older_than: datetime
    ) -> int:
        """Remove old completed/failed items"""
        to_remove = [
            item_id for item_id, item in self._items.items()
            if item.status in [DeliveryStatus.DELIVERED, DeliveryStatus.FAILED]
            and item.created_at < older_than
        ]

        for item_id in to_remove:
            del self._items[item_id]

        return len(to_remove)
