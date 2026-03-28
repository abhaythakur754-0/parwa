# Tests for Week 47 - Enterprise Webhooks & Events (Complete)
# Tests for all new webhook modules

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

# Import new modules - Builder 2
from enterprise.webhooks.event_publisher import EventPublisher, PublishStatus
from enterprise.webhooks.event_types import EventTypeRegistry, EventCategory, EventSeverity

# Import new modules - Builder 3
from enterprise.webhooks.retry_handler import RetryHandler, RetryConfig, RetryStatus
from enterprise.webhooks.delivery_queue import DeliveryQueue, DeliveryPriority, DeliveryStatus

# Import new modules - Builder 4
from enterprise.webhooks.event_replay import EventReplay, ReplayStatus
from enterprise.webhooks.event_sourcing import Event, EventStore as ESEventStore, AggregateRoot

# Import new modules - Builder 5
from enterprise.webhooks.success_tracker import SuccessTracker, DeliveryResult
from enterprise.webhooks.latency_monitor import LatencyMonitor, LatencyLevel


# ============== BUILDER 2: EVENT PUBLISHER TESTS ==============

class TestEventPublisher:
    @pytest.mark.asyncio
    async def test_publish_event(self):
        publisher = EventPublisher()
        event = await publisher.publish(
            event_type="user.created",
            topic="users",
            payload={"user_id": "123", "email": "test@example.com"}
        )
        assert event.event_type == "user.created"
        assert event.topic == "users"
        assert event.status == PublishStatus.PUBLISHED

    @pytest.mark.asyncio
    async def test_publish_batch(self):
        publisher = EventPublisher()
        events = await publisher.publish_batch([
            {"event_type": "test1", "topic": "test", "payload": {"id": 1}},
            {"event_type": "test2", "topic": "test", "payload": {"id": 2}},
            {"event_type": "test3", "topic": "test", "payload": {"id": 3}}
        ])
        assert len(events) == 3

    def test_get_event(self):
        publisher = EventPublisher()
        # Create event synchronously by adding to dict
        from enterprise.webhooks.event_publisher import PublishedEvent
        event = PublishedEvent(event_type="test", topic="test")
        publisher._published_events[event.id] = event
        result = publisher.get_event(event.id)
        assert result.id == event.id

    def test_get_events_by_topic(self):
        publisher = EventPublisher()
        from enterprise.webhooks.event_publisher import PublishedEvent
        e1 = PublishedEvent(event_type="t1", topic="users")
        e2 = PublishedEvent(event_type="t2", topic="orders")
        publisher._published_events[e1.id] = e1
        publisher._published_events[e2.id] = e2
        results = publisher.get_events_by_topic("users")
        assert len(results) == 1

    def test_get_events_by_type(self):
        publisher = EventPublisher()
        from enterprise.webhooks.event_publisher import PublishedEvent
        e1 = PublishedEvent(event_type="user.created", topic="test")
        e2 = PublishedEvent(event_type="user.deleted", topic="test")
        publisher._published_events[e1.id] = e1
        publisher._published_events[e2.id] = e2
        results = publisher.get_events_by_type("user.created")
        assert len(results) == 1

    def test_get_failed_events(self):
        publisher = EventPublisher()
        from enterprise.webhooks.event_publisher import PublishedEvent, PublishStatus
        e1 = PublishedEvent(event_type="t1", topic="test")
        e2 = PublishedEvent(event_type="t2", topic="test", status=PublishStatus.FAILED)
        publisher._published_events[e1.id] = e1
        publisher._published_events[e2.id] = e2
        results = publisher.get_failed_events()
        assert len(results) == 1

    def test_get_metrics(self):
        publisher = EventPublisher()
        metrics = publisher.get_metrics()
        assert "total_published" in metrics
        assert "total_failed" in metrics
        assert "by_topic" in metrics
        assert "by_type" in metrics


class TestEventTypes:
    def test_initialize_defaults(self):
        registry = EventTypeRegistry()
        registry.initialize_defaults()
        assert registry.exists("user.created")
        assert registry.exists("billing.payment_failed")
        assert registry.exists("integration.sync_completed")

    def test_register_custom_type(self):
        registry = EventTypeRegistry()
        from enterprise.webhooks.event_types import EventTypeDefinition
        custom = EventTypeDefinition(
            name="custom.event",
            category=EventCategory.CUSTOM,
            description="Custom event"
        )
        registry.register(custom)
        assert registry.exists("custom.event")

    def test_get_by_category(self):
        registry = EventTypeRegistry()
        registry.initialize_defaults()
        user_events = registry.get_by_category(EventCategory.USER)
        assert len(user_events) > 0

    def test_get_topics_for_event(self):
        registry = EventTypeRegistry()
        registry.initialize_defaults()
        topics = registry.get_topics_for_event("user.created")
        assert "users" in topics

    def test_get_severity(self):
        registry = EventTypeRegistry()
        registry.initialize_defaults()
        severity = registry.get_severity("security.suspicious_activity")
        assert severity == EventSeverity.HIGH


# ============== BUILDER 3: RETRY HANDLER TESTS ==============

class TestRetryHandler:
    def test_create_task(self):
        handler = RetryHandler()
        task = handler.create_task(
            task_id="task1",
            payload={"type": "webhook", "url": "https://example.com"}
        )
        assert task.id == "task1"
        assert task.status == RetryStatus.PENDING

    def test_calculate_delay(self):
        handler = RetryHandler()
        config = RetryConfig(
            initial_delay_seconds=1.0,
            max_delay_seconds=60.0,
            backoff_multiplier=2.0
        )
        # First retry
        d1 = handler.calculate_delay(1, config)
        assert d1 >= 0.9 and d1 <= 1.1  # ~1 second with jitter
        
        # Second retry
        d2 = handler.calculate_delay(2, config)
        assert d2 >= 1.8  # Should be around 2 seconds

    @pytest.mark.asyncio
    async def test_execute_success(self):
        handler = RetryHandler()
        task = handler.create_task("task1", {"url": "https://example.com"})
        result = await handler.execute_with_retry("task1", handler=lambda p: True)
        assert result.status == RetryStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_execute_with_retries(self):
        handler = RetryHandler()
        config = RetryConfig(max_attempts=3, initial_delay_seconds=0.1)
        task = handler.create_task("task1", {"url": "test"}, config=config)
        
        call_count = [0]
        def failing_handler(p):
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("Temporary error")
            return True
        
        result = await handler.execute_with_retry("task1", handler=failing_handler)
        assert result.status == RetryStatus.SUCCESS
        assert len(task.attempts) == 2

    def test_get_metrics(self):
        handler = RetryHandler()
        metrics = handler.get_metrics()
        assert "total_retries" in metrics
        assert "successful_retries" in metrics


# ============== BUILDER 3: DELIVERY QUEUE TESTS ==============

class TestDeliveryQueue:
    @pytest.mark.asyncio
    async def test_enqueue(self):
        queue = DeliveryQueue()
        item = await queue.enqueue(
            webhook_id="wh1",
            tenant_id="t1",
            url="https://example.com/webhook",
            payload={"event": "test"}
        )
        assert item.webhook_id == "wh1"
        assert item.status == DeliveryStatus.QUEUED

    @pytest.mark.asyncio
    async def test_dequeue(self):
        queue = DeliveryQueue()
        await queue.enqueue("wh1", "t1", "https://example.com", {"test": "data"})
        item = await queue.dequeue()
        assert item is not None
        assert item.status == DeliveryStatus.PROCESSING

    @pytest.mark.asyncio
    async def test_priority_order(self):
        queue = DeliveryQueue()
        await queue.enqueue("wh1", "t1", "url", {}, priority=DeliveryPriority.LOW)
        await queue.enqueue("wh2", "t1", "url", {}, priority=DeliveryPriority.URGENT)
        await queue.enqueue("wh3", "t1", "url", {}, priority=DeliveryPriority.NORMAL)
        
        first = await queue.dequeue()
        assert first.priority == DeliveryPriority.URGENT
        
        second = await queue.dequeue()
        assert second.priority == DeliveryPriority.NORMAL

    @pytest.mark.asyncio
    async def test_mark_delivered(self):
        queue = DeliveryQueue()
        item = await queue.enqueue("wh1", "t1", "url", {})
        await queue.dequeue()
        result = await queue.mark_delivered(item.id)
        assert result is True
        assert item.status == DeliveryStatus.DELIVERED

    @pytest.mark.asyncio
    async def test_mark_failed_with_retry(self):
        queue = DeliveryQueue()
        item = await queue.enqueue("wh1", "t1", "url", {})
        await queue.dequeue()
        await queue.mark_failed(item.id, retry=True)
        assert item.status == DeliveryStatus.RETRYING
        assert item.retry_count == 1

    @pytest.mark.asyncio
    async def test_size(self):
        queue = DeliveryQueue()
        assert await queue.size() == 0
        await queue.enqueue("wh1", "t1", "url", {})
        assert await queue.size() == 1


# ============== BUILDER 4: EVENT REPLAY TESTS ==============

class TestEventReplay:
    def test_create_job(self):
        replay = EventReplay()
        job = replay.create_job(
            tenant_id="t1",
            name="Replay Yesterday",
            start_time=datetime.utcnow() - timedelta(days=1),
            end_time=datetime.utcnow()
        )
        assert job.tenant_id == "t1"
        assert job.status == ReplayStatus.PENDING

    def test_cancel_job(self):
        replay = EventReplay()
        job = replay.create_job("t1", "Test", datetime.utcnow(), datetime.utcnow())
        result = replay.cancel_job(job.id)
        assert result is True
        assert job.status == ReplayStatus.CANCELLED

    def test_get_job_progress(self):
        replay = EventReplay()
        job = replay.create_job("t1", "Test", datetime.utcnow(), datetime.utcnow())
        progress = replay.get_job_progress(job.id)
        assert "progress_percent" in progress
        assert "status" in progress

    def test_get_jobs_by_tenant(self):
        replay = EventReplay()
        replay.create_job("t1", "Job1", datetime.utcnow(), datetime.utcnow())
        replay.create_job("t1", "Job2", datetime.utcnow(), datetime.utcnow())
        replay.create_job("t2", "Job3", datetime.utcnow(), datetime.utcnow())
        jobs = replay.get_jobs_by_tenant("t1")
        assert len(jobs) == 2

    def test_get_metrics(self):
        replay = EventReplay()
        metrics = replay.get_metrics()
        assert "total_jobs" in metrics
        assert "completed_jobs" in metrics


# ============== BUILDER 4: EVENT SOURCING TESTS ==============

class TestEventSourcing:
    def test_create_event(self):
        event = Event(
            aggregate_id="user-123",
            aggregate_type="User",
            event_type="created",
            version=1,
            data={"name": "John", "email": "john@example.com"}
        )
        assert event.aggregate_id == "user-123"
        assert event.version == 1

    @pytest.mark.asyncio
    async def test_event_store_append(self):
        store = ESEventStore()
        event = Event(aggregate_id="agg1", event_type="created", version=1)
        await store.append(event)
        events = await store.get_events("agg1")
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_event_store_version_filter(self):
        store = ESEventStore()
        for i in range(1, 4):
            await store.append(Event(aggregate_id="agg1", event_type=f"event_{i}", version=i))
        
        events = await store.get_events("agg1", from_version=1)
        assert len(events) == 2  # Events with version > 1


# ============== BUILDER 5: SUCCESS TRACKER TESTS ==============

class TestSuccessTracker:
    def test_record_success(self):
        tracker = SuccessTracker()
        record = tracker.record_delivery(
            webhook_id="wh1",
            tenant_id="t1",
            url="https://example.com",
            result=DeliveryResult.SUCCESS,
            response_time_ms=150.5
        )
        assert record.result == DeliveryResult.SUCCESS

    def test_record_failure(self):
        tracker = SuccessTracker()
        record = tracker.record_delivery(
            webhook_id="wh1",
            tenant_id="t1",
            url="https://example.com",
            result=DeliveryResult.FAILURE,
            error_message="Connection timeout"
        )
        assert record.result == DeliveryResult.FAILURE

    def test_get_success_rate(self):
        tracker = SuccessTracker()
        tracker.record_delivery("wh1", "t1", "url", DeliveryResult.SUCCESS)
        tracker.record_delivery("wh1", "t1", "url", DeliveryResult.SUCCESS)
        tracker.record_delivery("wh1", "t1", "url", DeliveryResult.FAILURE)
        rate = tracker.get_success_rate("wh1")
        assert rate == pytest.approx(66.67, rel=0.1)

    def test_get_failing_webhooks(self):
        tracker = SuccessTracker()
        # wh1 has 50% success rate
        tracker.record_delivery("wh1", "t1", "url", DeliveryResult.SUCCESS)
        tracker.record_delivery("wh1", "t1", "url", DeliveryResult.FAILURE)
        # wh2 has 100% success rate
        tracker.record_delivery("wh2", "t1", "url", DeliveryResult.SUCCESS)
        
        failing = tracker.get_failing_webhooks(threshold=60)
        assert len(failing) == 1
        assert failing[0].webhook_id == "wh1"

    def test_get_global_stats(self):
        tracker = SuccessTracker()
        tracker.record_delivery("wh1", "t1", "url", DeliveryResult.SUCCESS)
        tracker.record_delivery("wh2", "t1", "url", DeliveryResult.FAILURE)
        stats = tracker.get_global_stats()
        assert stats["total_deliveries"] == 2
        assert stats["successful"] == 1
        assert stats["failed"] == 1

    def test_get_error_summary(self):
        tracker = SuccessTracker()
        tracker.record_delivery("wh1", "t1", "url", DeliveryResult.FAILURE, error_message="Timeout")
        tracker.record_delivery("wh1", "t1", "url", DeliveryResult.FAILURE, error_message="Timeout")
        tracker.record_delivery("wh1", "t1", "url", DeliveryResult.FAILURE, error_message="500 Error")
        
        summary = tracker.get_error_summary("wh1")
        assert summary["Timeout"] == 2
        assert summary["500 Error"] == 1


# ============== BUILDER 5: LATENCY MONITOR TESTS ==============

class TestLatencyMonitor:
    def test_record_latency(self):
        monitor = LatencyMonitor()
        record = monitor.record_latency("wh1", "t1", "https://example.com", 150.5)
        assert record.latency_ms == 150.5
        assert record.level == LatencyLevel.GOOD

    def test_classify_latency(self):
        monitor = LatencyMonitor()
        assert monitor.classify_latency(50) == LatencyLevel.EXCELLENT
        assert monitor.classify_latency(200) == LatencyLevel.GOOD
        assert monitor.classify_latency(750) == LatencyLevel.MODERATE
        assert monitor.classify_latency(2000) == LatencyLevel.SLOW
        assert monitor.classify_latency(5000) == LatencyLevel.CRITICAL

    def test_get_stats(self):
        monitor = LatencyMonitor()
        monitor.record_latency("wh1", "t1", "url", 100)
        monitor.record_latency("wh1", "t1", "url", 200)
        monitor.record_latency("wh1", "t1", "url", 300)
        
        stats = monitor.get_stats("wh1")
        assert stats.count == 3
        assert stats.min_ms == 100
        assert stats.max_ms == 300
        assert stats.avg_ms == 200

    def test_get_latency_distribution(self):
        monitor = LatencyMonitor()
        monitor.record_latency("wh1", "t1", "url", 50)   # excellent
        monitor.record_latency("wh1", "t1", "url", 200)  # good
        monitor.record_latency("wh1", "t1", "url", 1500) # slow
        
        dist = monitor.get_latency_distribution("wh1")
        assert dist["excellent"] == 1
        assert dist["good"] == 1
        assert dist["slow"] == 1

    def test_get_summary(self):
        monitor = LatencyMonitor()
        monitor.record_latency("wh1", "t1", "url", 100)
        monitor.record_latency("wh2", "t1", "url", 200)
        
        summary = monitor.get_summary()
        assert summary["total_webhooks"] == 2
        assert summary["global_avg_ms"] == 150

    def test_get_slow_webhooks(self):
        monitor = LatencyMonitor()
        monitor.record_latency("wh1", "t1", "url", 500)   # avg will be 500
        monitor.record_latency("wh2", "t1", "url", 50)    # avg will be 50
        
        slow = monitor.get_slow_webhooks(threshold_ms=100)
        assert len(slow) == 1
        assert slow[0].webhook_id == "wh1"
