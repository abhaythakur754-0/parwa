"""Tests for Event Bus, Delivery Engine, Event Store, and Analytics"""
import pytest
import asyncio
from datetime import datetime, timedelta
from enterprise.webhooks.event_bus import EventBus, Event
from enterprise.webhooks.delivery_engine import DeliveryEngine, DeliveryStatus, RetryConfig
from enterprise.webhooks.event_store import EventStore, StoredEvent
from enterprise.webhooks.webhook_analytics import WebhookAnalytics

class TestEventBus:
    @pytest.fixture
    def bus(self):
        return EventBus()

    def test_subscribe(self, bus):
        def handler(event):
            pass
        bus.subscribe("test.event", handler)
        assert "test.event" in bus._subscribers

    def test_publish(self, bus):
        received = []
        def handler(event):
            received.append(event)
        bus.subscribe("test.event", handler)
        bus.publish("test.event", "tenant_001", {"id": 1})
        assert len(received) == 1

    def test_publish_wildcard(self, bus):
        received = []
        def handler(event):
            received.append(event)
        bus.subscribe("*", handler)
        bus.publish("any.event", "tenant_001", {"id": 1})
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_publish_async(self, bus):
        received = []
        async def handler(event):
            received.append(event)
        bus.subscribe_async("test.event", handler)
        await bus.publish_async("test.event", "tenant_001", {"id": 1})
        assert len(received) == 1

    def test_get_event(self, bus):
        event = bus.publish("test.event", "tenant_001", {"id": 1})
        retrieved = bus.get_event(event.event_id)
        assert retrieved is not None

    def test_get_events_by_type(self, bus):
        bus.publish("type.a", "tenant_001", {"id": 1})
        bus.publish("type.b", "tenant_001", {"id": 2})
        events = bus.get_events_by_type("type.a")
        assert len(events) == 1

    def test_get_events_by_tenant(self, bus):
        bus.publish("test.event", "tenant_001", {"id": 1})
        bus.publish("test.event", "tenant_002", {"id": 2})
        events = bus.get_events_by_tenant("tenant_001")
        assert len(events) == 1

    def test_get_metrics(self, bus):
        bus.publish("test.event", "tenant_001", {"id": 1})
        metrics = bus.get_metrics()
        assert metrics["events_published"] == 1


class TestDeliveryEngine:
    @pytest.fixture
    def engine(self):
        return DeliveryEngine(retry_config=RetryConfig(max_attempts=3, base_delay_seconds=0.1))

    def test_queue_delivery(self, engine):
        attempt = engine.queue_delivery("wh_001", "https://example.com/webhook", {"event": "test"}, "evt_001")
        assert attempt.status == DeliveryStatus.PENDING
        assert attempt.webhook_id == "wh_001"

    def test_get_attempt(self, engine):
        created = engine.queue_delivery("wh_001", "https://example.com/webhook", {"event": "test"}, "evt_001")
        retrieved = engine.get_attempt(created.attempt_id)
        assert retrieved is not None

    def test_get_pending_attempts(self, engine):
        engine.queue_delivery("wh_001", "https://example.com/webhook", {"event": "test"}, "evt_001")
        pending = engine.get_pending_attempts()
        assert len(pending) == 1

    def test_get_metrics(self, engine):
        engine.queue_delivery("wh_001", "https://example.com/webhook", {"event": "test"}, "evt_001")
        metrics = engine.get_metrics()
        assert metrics["total_deliveries"] == 1


class TestEventStore:
    @pytest.fixture
    def store(self):
        return EventStore(max_events=100)

    def test_store(self, store):
        event = store.store("evt_001", "test.event", "tenant_001", {"id": 1})
        assert event.event_id == "evt_001"
        assert event.sequence_number == 1

    def test_get(self, store):
        store.store("evt_001", "test.event", "tenant_001", {"id": 1})
        event = store.get("evt_001")
        assert event is not None

    def test_get_by_tenant(self, store):
        store.store("evt_001", "test.event", "tenant_001", {"id": 1})
        store.store("evt_002", "test.event", "tenant_002", {"id": 2})
        events = store.get_by_tenant("tenant_001")
        assert len(events) == 1

    def test_get_by_type(self, store):
        store.store("evt_001", "type.a", "tenant_001", {"id": 1})
        store.store("evt_002", "type.b", "tenant_001", {"id": 2})
        events = store.get_by_type("type.a")
        assert len(events) == 1

    def test_get_since_sequence(self, store):
        store.store("evt_001", "test.event", "tenant_001", {"id": 1})
        store.store("evt_002", "test.event", "tenant_001", {"id": 2})
        events = store.get_since_sequence(0)
        assert len(events) == 2

    def test_replay_events(self, store):
        store.store("evt_001", "test.event", "tenant_001", {"id": 1})
        replayed = []
        store.replay_events("tenant_001", lambda e: replayed.append(e))
        assert len(replayed) == 1

    def test_get_statistics(self, store):
        store.store("evt_001", "test.event", "tenant_001", {"id": 1})
        stats = store.get_statistics()
        assert stats["total_events"] == 1


class TestWebhookAnalytics:
    @pytest.fixture
    def analytics(self):
        return WebhookAnalytics()

    def test_record_delivery(self, analytics):
        analytics.record_delivery("wh_001", True, 100.0)
        metrics = analytics.get_webhook_metrics("wh_001")
        assert metrics["total_deliveries"] == 1
        assert metrics["success_rate"] == 100.0

    def test_record_failure(self, analytics):
        analytics.record_delivery("wh_001", True, 100.0)
        analytics.record_delivery("wh_001", False, 200.0)
        metrics = analytics.get_webhook_metrics("wh_001")
        assert metrics["success_rate"] == 50.0

    def test_get_all_metrics(self, analytics):
        analytics.record_delivery("wh_001", True, 100.0)
        analytics.record_delivery("wh_002", True, 150.0)
        metrics = analytics.get_all_metrics()
        assert metrics["total_deliveries"] == 2

    def test_get_latency_stats(self, analytics):
        analytics.record_delivery("wh_001", True, 100.0)
        analytics.record_delivery("wh_001", True, 200.0)
        analytics.record_delivery("wh_001", True, 300.0)
        stats = analytics.get_latency_stats()
        assert stats["avg"] == 200.0
        assert stats["min"] == 100.0
        assert stats["max"] == 300.0

    def test_get_hourly_stats(self, analytics):
        analytics.record_delivery("wh_001", True, 100.0)
        hourly = analytics.get_hourly_stats()
        assert len(hourly) > 0

    def test_get_failing_webhooks(self, analytics):
        analytics.record_delivery("wh_001", False, 100.0)
        analytics.record_delivery("wh_001", False, 100.0)
        failing = analytics.get_failing_webhooks(threshold=90.0)
        assert len(failing) == 1

    def test_clear_metrics(self, analytics):
        analytics.record_delivery("wh_001", True, 100.0)
        count = analytics.clear_metrics()
        assert count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
