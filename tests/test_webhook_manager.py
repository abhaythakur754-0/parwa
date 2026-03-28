"""
Week 58 - Builder 3 Tests: Webhook Manager Module
Unit tests for Webhook Registry, Dispatcher, and Verifier
"""

import pytest
import time
from parwa_integration_hub.webhook_registry import (
    WebhookRegistry, WebhookEndpoint, WebhookStatus,
    WebhookDispatcher, WebhookDelivery, DeliveryStatus,
    WebhookVerifier
)


class TestWebhookRegistry:
    """Tests for WebhookRegistry class"""

    @pytest.fixture
    def registry(self):
        """Create test registry"""
        return WebhookRegistry()

    def test_register_webhook(self, registry):
        """Test webhook registration"""
        endpoint = registry.register(
            name="test-webhook",
            url="https://example.com/webhook",
            events=["user.created", "user.updated"]
        )

        assert endpoint.id is not None
        assert endpoint.name == "test-webhook"
        assert endpoint.status == WebhookStatus.ACTIVE

    def test_unregister_webhook(self, registry):
        """Test webhook unregistration"""
        endpoint = registry.register(
            name="test-webhook",
            url="https://example.com/webhook",
            events=["user.created"]
        )

        result = registry.unregister(endpoint.id)
        assert result is True
        assert endpoint.id not in registry.endpoints

    def test_get_endpoint(self, registry):
        """Test get endpoint by ID"""
        endpoint = registry.register(
            name="test-webhook",
            url="https://example.com/webhook",
            events=["user.created"]
        )

        retrieved = registry.get_endpoint(endpoint.id)
        assert retrieved.name == "test-webhook"

    def test_get_nonexistent_endpoint(self, registry):
        """Test get nonexistent endpoint"""
        endpoint = registry.get_endpoint("nonexistent-id")
        assert endpoint is None

    def test_get_endpoints_for_event(self, registry):
        """Test get endpoints subscribed to event"""
        registry.register(
            name="webhook1",
            url="https://example.com/hook1",
            events=["user.created", "user.deleted"]
        )
        registry.register(
            name="webhook2",
            url="https://example.com/hook2",
            events=["user.created"]
        )

        endpoints = registry.get_endpoints_for_event("user.created")
        assert len(endpoints) == 2

    def test_pause_webhook(self, registry):
        """Test pausing webhook"""
        endpoint = registry.register(
            name="test-webhook",
            url="https://example.com/webhook",
            events=["user.created"]
        )

        result = registry.pause(endpoint.id)
        assert result is True
        assert registry.endpoints[endpoint.id].status == WebhookStatus.PAUSED

    def test_resume_webhook(self, registry):
        """Test resuming webhook"""
        endpoint = registry.register(
            name="test-webhook",
            url="https://example.com/webhook",
            events=["user.created"]
        )
        registry.pause(endpoint.id)

        result = registry.resume(endpoint.id)
        assert result is True
        assert registry.endpoints[endpoint.id].status == WebhookStatus.ACTIVE

    def test_disable_webhook(self, registry):
        """Test disabling webhook"""
        endpoint = registry.register(
            name="test-webhook",
            url="https://example.com/webhook",
            events=["user.created"]
        )

        result = registry.disable(endpoint.id)
        assert result is True
        assert registry.endpoints[endpoint.id].status == WebhookStatus.DISABLED

    def test_rotate_secret(self, registry):
        """Test secret rotation"""
        endpoint = registry.register(
            name="test-webhook",
            url="https://example.com/webhook",
            events=["user.created"]
        )
        old_secret = endpoint.secret

        new_secret = registry.rotate_secret(endpoint.id)
        assert new_secret is not None
        assert new_secret != old_secret

    def test_list_endpoints(self, registry):
        """Test list endpoints"""
        registry.register("hook1", "https://example.com/1", ["event1"])
        registry.register("hook2", "https://example.com/2", ["event2"])

        endpoints = registry.list_endpoints()
        assert len(endpoints) == 2

    def test_get_stats(self, registry):
        """Test get registry statistics"""
        registry.register("hook1", "https://example.com/1", ["event1"])
        registry.register("hook2", "https://example.com/2", ["event2"])

        stats = registry.get_stats()
        assert stats["total_endpoints"] == 2
        assert stats["active_endpoints"] == 2


class TestWebhookDispatcher:
    """Tests for WebhookDispatcher class"""

    @pytest.fixture
    def dispatcher(self):
        """Create test dispatcher"""
        registry = WebhookRegistry()
        return WebhookDispatcher(registry)

    @pytest.fixture
    def registry_with_endpoint(self):
        """Create registry with registered webhook"""
        registry = WebhookRegistry()
        registry.register(
            name="test-webhook",
            url="https://example.com/webhook",
            events=["user.created"]
        )
        return registry

    def test_dispatch_event(self):
        """Test event dispatch"""
        registry = WebhookRegistry()
        registry.register(
            name="test-webhook",
            url="https://example.com/webhook",
            events=["user.created"]
        )
        dispatcher = WebhookDispatcher(registry)

        delivery_ids = dispatcher.dispatch(
            "user.created",
            {"user_id": 123, "email": "test@example.com"}
        )

        assert len(delivery_ids) == 1

    def test_dispatch_to_multiple_endpoints(self):
        """Test dispatch to multiple endpoints"""
        registry = WebhookRegistry()
        registry.register("hook1", "https://example.com/1", ["user.created"])
        registry.register("hook2", "https://example.com/2", ["user.created"])
        dispatcher = WebhookDispatcher(registry)

        delivery_ids = dispatcher.dispatch("user.created", {"user_id": 123})

        assert len(delivery_ids) == 2

    def test_dispatch_no_subscribers(self, dispatcher):
        """Test dispatch with no subscribers"""
        delivery_ids = dispatcher.dispatch("nonexistent.event", {"data": "test"})
        assert len(delivery_ids) == 0

    def test_process_delivery(self):
        """Test processing delivery"""
        registry = WebhookRegistry()
        endpoint = registry.register(
            name="test-webhook",
            url="https://example.com/webhook",
            events=["user.created"]
        )
        dispatcher = WebhookDispatcher(registry)

        delivery_ids = dispatcher.dispatch("user.created", {"user_id": 123})
        result = dispatcher.process_delivery(delivery_ids[0])

        assert result is True

    def test_get_delivery(self):
        """Test get delivery by ID"""
        registry = WebhookRegistry()
        registry.register("hook", "https://example.com/webhook", ["user.created"])
        dispatcher = WebhookDispatcher(registry)

        delivery_ids = dispatcher.dispatch("user.created", {"user_id": 123})

        delivery = dispatcher.get_delivery(delivery_ids[0])
        assert delivery is not None
        assert delivery.event == "user.created"

    def test_get_pending_count(self):
        """Test get pending count"""
        registry = WebhookRegistry()
        registry.register("hook", "https://example.com/webhook", ["user.created"])
        dispatcher = WebhookDispatcher(registry)

        dispatcher.dispatch("user.created", {"user_id": 123})

        count = dispatcher.get_pending_count()
        assert count >= 1

    def test_get_stats(self):
        """Test get dispatcher statistics"""
        registry = WebhookRegistry()
        registry.register("hook", "https://example.com/webhook", ["user.created"])
        dispatcher = WebhookDispatcher(registry)

        dispatcher.dispatch("user.created", {"user_id": 123})

        stats = dispatcher.get_stats()
        assert isinstance(stats, dict)


class TestWebhookVerifier:
    """Tests for WebhookVerifier class"""

    @pytest.fixture
    def verifier(self):
        """Create test verifier"""
        return WebhookVerifier()

    def test_generate_signature(self, verifier):
        """Test signature generation"""
        secret = "test-secret"
        payload = '{"user_id": 123}'

        signature = verifier.generate_signature(secret, payload)

        assert signature is not None
        assert "t=" in signature
        assert "v1=" in signature

    def test_verify_valid_signature(self, verifier):
        """Test valid signature verification"""
        secret = "test-secret"
        payload = '{"user_id": 123}'

        signature = verifier.generate_signature(secret, payload)
        result = verifier.verify_signature(secret, payload, signature)

        assert result is True

    def test_verify_invalid_signature(self, verifier):
        """Test invalid signature verification"""
        secret = "test-secret"
        payload = '{"user_id": 123}'

        signature = verifier.generate_signature(secret, payload)
        result = verifier.verify_signature("wrong-secret", payload, signature)

        assert result is False

    def test_verify_tampered_payload(self, verifier):
        """Test tampered payload detection"""
        secret = "test-secret"
        payload = '{"user_id": 123}'

        signature = verifier.generate_signature(secret, payload)
        result = verifier.verify_signature(secret, '{"user_id": 456}', signature)

        assert result is False

    def test_verify_timestamp(self, verifier):
        """Test timestamp verification"""
        now = str(int(time.time()))
        assert verifier.verify_timestamp(now) is True

        old = str(int(time.time()) - 1000)
        assert verifier.verify_timestamp(old) is False

    def test_parse_signature_header(self, verifier):
        """Test parsing signature header"""
        header = "t=1234567890,v1=abc123def456"

        parts = verifier.parse_signature_header(header)

        assert parts["t"] == "1234567890"
        assert parts["v1"] == "abc123def456"

    def test_get_stats(self, verifier):
        """Test get verification statistics"""
        secret = "test-secret"
        payload = '{"data": "test"}'

        signature = verifier.generate_signature(secret, payload)
        verifier.verify_signature(secret, payload, signature)
        verifier.verify_signature("wrong", payload, signature)

        stats = verifier.get_stats()
        assert "total" in stats
