"""
Tests for Webhook Management
Enterprise Integration Hub - Week 43 Builder 4
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import json

from enterprise.integrations.webhook_manager import (
    WebhookManager,
    WebhookEndpoint,
    WebhookDelivery,
    WebhookStatus,
    EventType
)
from enterprise.integrations.webhook_signer import (
    WebhookSigner,
    SignatureResult,
    MultiSigner
)
from enterprise.integrations.webhook_retry import (
    RetryCalculator,
    RetryConfig,
    RetryStrategy,
    RetryState,
    WebhookRetryQueue
)


# Test Fixtures
@pytest.fixture
def webhook_manager():
    """Create a test webhook manager"""
    return WebhookManager()


@pytest.fixture
def webhook_signer():
    """Create a test webhook signer"""
    return WebhookSigner()


@pytest.fixture
def retry_config():
    """Create a test retry configuration"""
    return RetryConfig(
        max_retries=5,
        strategy=RetryStrategy.EXPONENTIAL_JITTER,
        base_delay_seconds=1.0
    )


# WebhookManager Tests
class TestWebhookManager:
    """Tests for WebhookManager"""
    
    def test_manager_initialization(self, webhook_manager):
        """Test manager initializes correctly"""
        assert webhook_manager is not None
        assert len(webhook_manager._endpoints) == 0
    
    def test_register_webhook(self, webhook_manager):
        """Test webhook registration"""
        endpoint = webhook_manager.register_webhook(
            name="test_webhook",
            url="https://example.com/webhook",
            events=["ticket.created", "ticket.updated"]
        )
        
        assert endpoint.id is not None
        assert endpoint.name == "test_webhook"
        assert endpoint.url == "https://example.com/webhook"
        assert endpoint.status == WebhookStatus.ACTIVE
        assert len(endpoint.events) == 2
    
    def test_register_webhook_auto_secret(self, webhook_manager):
        """Test auto-generation of webhook secret"""
        endpoint = webhook_manager.register_webhook(
            name="test",
            url="https://example.com/webhook",
            events=["ticket.created"]
        )
        
        assert endpoint.secret is not None
        assert len(endpoint.secret) == 64  # Two UUIDs concatenated
    
    def test_get_webhook(self, webhook_manager):
        """Test getting a webhook by ID"""
        registered = webhook_manager.register_webhook(
            name="test",
            url="https://example.com/webhook",
            events=["ticket.created"]
        )
        
        retrieved = webhook_manager.get_webhook(registered.id)
        
        assert retrieved is not None
        assert retrieved.id == registered.id
    
    def test_get_nonexistent_webhook(self, webhook_manager):
        """Test getting a non-existent webhook"""
        result = webhook_manager.get_webhook("nonexistent")
        assert result is None
    
    def test_update_webhook(self, webhook_manager):
        """Test updating a webhook"""
        endpoint = webhook_manager.register_webhook(
            name="test",
            url="https://example.com/webhook",
            events=["ticket.created"]
        )
        
        updated = webhook_manager.update_webhook(
            endpoint.id,
            name="updated_name",
            events=["ticket.created", "ticket.updated", "ticket.resolved"]
        )
        
        assert updated.name == "updated_name"
        assert len(updated.events) == 3
    
    def test_delete_webhook(self, webhook_manager):
        """Test deleting a webhook"""
        endpoint = webhook_manager.register_webhook(
            name="test",
            url="https://example.com/webhook",
            events=["ticket.created"]
        )
        
        result = webhook_manager.delete_webhook(endpoint.id)
        assert result is True
        
        retrieved = webhook_manager.get_webhook(endpoint.id)
        assert retrieved is None
    
    def test_list_webhooks(self, webhook_manager):
        """Test listing webhooks"""
        webhook_manager.register_webhook(
            name="webhook1",
            url="https://example1.com/webhook",
            events=["ticket.created"]
        )
        webhook_manager.register_webhook(
            name="webhook2",
            url="https://example2.com/webhook",
            events=["ticket.updated"]
        )
        
        webhooks = webhook_manager.list_webhooks()
        assert len(webhooks) == 2
    
    def test_list_webhooks_by_status(self, webhook_manager):
        """Test filtering webhooks by status"""
        endpoint = webhook_manager.register_webhook(
            name="test",
            url="https://example.com/webhook",
            events=["ticket.created"]
        )
        
        active = webhook_manager.list_webhooks(status=WebhookStatus.ACTIVE)
        assert len(active) == 1
    
    def test_list_webhooks_by_event(self, webhook_manager):
        """Test filtering webhooks by event type"""
        webhook_manager.register_webhook(
            name="webhook1",
            url="https://example1.com/webhook",
            events=["ticket.created", "ticket.updated"]
        )
        webhook_manager.register_webhook(
            name="webhook2",
            url="https://example2.com/webhook",
            events=["customer.created"]
        )
        
        ticket_webhooks = webhook_manager.list_webhooks(event_type="ticket.created")
        assert len(ticket_webhooks) == 1
    
    @pytest.mark.asyncio
    async def test_trigger_event(self, webhook_manager):
        """Test triggering a webhook event"""
        webhook_manager.register_webhook(
            name="test",
            url="https://example.com/webhook",
            events=["ticket.created"]
        )
        
        deliveries = await webhook_manager.trigger_event(
            event_type="ticket.created",
            payload={"ticket_id": "123", "subject": "Test ticket"}
        )
        
        assert isinstance(deliveries, list)
    
    def test_generate_signature(self, webhook_manager):
        """Test signature generation"""
        endpoint = webhook_manager.register_webhook(
            name="test",
            url="https://example.com/webhook",
            events=["ticket.created"]
        )
        
        payload = {"test": "data"}
        signature = webhook_manager._generate_signature(endpoint.secret, payload)
        
        assert signature.startswith("sha256=")
        assert len(signature) > 10
    
    def test_verify_signature(self, webhook_manager):
        """Test signature verification"""
        endpoint = webhook_manager.register_webhook(
            name="test",
            url="https://example.com/webhook",
            events=["ticket.created"]
        )
        
        payload = {"test": "data"}
        signature = webhook_manager._generate_signature(endpoint.secret, payload)
        
        assert webhook_manager.verify_signature(endpoint.secret, payload, signature)
        assert not webhook_manager.verify_signature("wrong_secret", payload, signature)


# WebhookEndpoint Tests
class TestWebhookEndpoint:
    """Tests for WebhookEndpoint"""
    
    def test_endpoint_creation(self):
        """Test endpoint can be created"""
        endpoint = WebhookEndpoint(
            id="test-id",
            name="test",
            url="https://example.com/webhook",
            secret="test_secret",
            events=["ticket.created"]
        )
        
        assert endpoint.id == "test-id"
        assert endpoint.name == "test"
        assert endpoint.status == WebhookStatus.ACTIVE
    
    def test_endpoint_to_dict(self):
        """Test endpoint serialization"""
        endpoint = WebhookEndpoint(
            id="test-id",
            name="test",
            url="https://example.com/webhook",
            secret="secret",
            events=["ticket.created"]
        )
        
        data = endpoint.to_dict()
        
        assert data["id"] == "test-id"
        assert data["name"] == "test"
        assert "secret" not in data  # Don't expose secret


# WebhookDelivery Tests
class TestWebhookDelivery:
    """Tests for WebhookDelivery"""
    
    def test_delivery_creation(self):
        """Test delivery can be created"""
        delivery = WebhookDelivery(
            id="delivery-id",
            endpoint_id="endpoint-id",
            event_type="ticket.created",
            payload={"test": "data"},
            status="pending"
        )
        
        assert delivery.id == "delivery-id"
        assert delivery.status == "pending"
    
    def test_delivery_to_dict(self):
        """Test delivery serialization"""
        delivery = WebhookDelivery(
            id="delivery-id",
            endpoint_id="endpoint-id",
            event_type="ticket.created",
            payload={"test": "data"},
            status="delivered",
            response_code=200
        )
        
        data = delivery.to_dict()
        
        assert data["id"] == "delivery-id"
        assert data["status"] == "delivered"
        assert data["response_code"] == 200


# WebhookSigner Tests
class TestWebhookSigner:
    """Tests for WebhookSigner"""
    
    def test_signer_initialization(self, webhook_signer):
        """Test signer initializes correctly"""
        assert webhook_signer.default_algorithm == "sha256"
    
    def test_sign_payload(self, webhook_signer):
        """Test payload signing"""
        secret = "test_secret"
        payload = {"test": "data"}
        
        signature = webhook_signer.sign(secret, payload)
        
        assert signature is not None
        # Signature includes timestamp by default
        assert "v1=" in signature
    
    def test_sign_with_timestamp(self, webhook_signer):
        """Test signing with timestamp"""
        secret = "test_secret"
        payload = {"test": "data"}
        
        signature = webhook_signer.sign(secret, payload, include_timestamp=True)
        
        assert "t=" in signature
        assert "v1=" in signature
    
    def test_verify_valid_signature(self, webhook_signer):
        """Test verifying a valid signature"""
        secret = "test_secret"
        payload = {"test": "data"}
        
        signature = webhook_signer.sign(secret, payload)
        result = webhook_signer.verify(secret, payload, signature)
        
        assert result.valid is True
    
    def test_verify_invalid_signature(self, webhook_signer):
        """Test verifying an invalid signature"""
        secret = "test_secret"
        payload = {"test": "data"}
        
        signature = webhook_signer.sign(secret, payload)
        result = webhook_signer.verify("wrong_secret", payload, signature)
        
        assert result.valid is False
    
    def test_verify_expired_signature(self, webhook_signer):
        """Test verifying an expired timestamped signature"""
        secret = "test_secret"
        payload = {"test": "data"}
        
        # Create signature with old timestamp
        old_signature = "t=1000000000,v1=abc123"  # Very old timestamp
        
        result = webhook_signer.verify(
            secret,
            payload,
            old_signature,
            max_age_seconds=60
        )
        
        assert result.valid is False
        assert "expired" in result.error.lower()
    
    def test_create_signature_headers(self, webhook_signer):
        """Test creating signature headers"""
        secret = "test_secret"
        payload = {"test": "data"}
        
        headers = webhook_signer.create_signature_headers(secret, payload, webhook_id="test-id")
        
        assert "X-Signature" in headers
        assert "X-Signature-Algorithm" in headers
        assert headers["X-Webhook-ID"] == "test-id"


# MultiSigner Tests
class TestMultiSigner:
    """Tests for MultiSigner"""
    
    def test_add_key(self):
        """Test adding signing keys"""
        signer = MultiSigner()
        signer.add_key("key1", "secret1", is_primary=True)
        
        assert signer._primary_key == "key1"
    
    def test_remove_key(self):
        """Test removing signing keys"""
        signer = MultiSigner()
        signer.add_key("key1", "secret1", is_primary=True)
        signer.add_key("key2", "secret2")
        
        signer.remove_key("key1")
        
        assert signer._primary_key == "key2"


# RetryConfig Tests
class TestRetryConfig:
    """Tests for RetryConfig"""
    
    def test_config_defaults(self):
        """Test default configuration values"""
        config = RetryConfig()
        
        assert config.max_retries == 5
        assert config.strategy == RetryStrategy.EXPONENTIAL_JITTER
        assert config.base_delay_seconds == 1.0
        assert config.max_delay_seconds == 300.0
    
    def test_config_to_dict(self):
        """Test config serialization"""
        config = RetryConfig(max_retries=3)
        data = config.to_dict()
        
        assert data["max_retries"] == 3
        assert data["strategy"] == "exponential_jitter"


# RetryCalculator Tests
class TestRetryCalculator:
    """Tests for RetryCalculator"""
    
    def test_calculator_initialization(self, retry_config):
        """Test calculator initializes correctly"""
        calculator = RetryCalculator(retry_config)
        assert calculator.config is not None
    
    def test_calculate_fixed_delay(self):
        """Test fixed delay calculation"""
        config = RetryConfig(strategy=RetryStrategy.FIXED, base_delay_seconds=2.0)
        calculator = RetryCalculator(config)
        
        delay = calculator.calculate_delay(1)
        assert delay == 2.0
        
        delay = calculator.calculate_delay(5)
        assert delay == 2.0
    
    def test_calculate_linear_delay(self):
        """Test linear delay calculation"""
        config = RetryConfig(strategy=RetryStrategy.LINEAR, base_delay_seconds=1.0)
        calculator = RetryCalculator(config)
        
        delay = calculator.calculate_delay(1)
        assert delay == 1.0
        
        delay = calculator.calculate_delay(3)
        assert delay == 3.0
    
    def test_calculate_exponential_delay(self):
        """Test exponential delay calculation"""
        config = RetryConfig(strategy=RetryStrategy.EXPONENTIAL, base_delay_seconds=1.0)
        calculator = RetryCalculator(config)
        
        delay = calculator.calculate_delay(1)
        assert delay == 1.0
        
        delay = calculator.calculate_delay(2)
        assert delay == 2.0
        
        delay = calculator.calculate_delay(3)
        assert delay == 4.0
    
    def test_max_delay_cap(self):
        """Test maximum delay cap"""
        config = RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL,
            base_delay_seconds=1.0,
            max_delay_seconds=10.0
        )
        calculator = RetryCalculator(config)
        
        delay = calculator.calculate_delay(10)  # Would be 512 without cap
        assert delay == 10.0
    
    def test_should_retry(self, retry_config):
        """Test retry decision logic"""
        calculator = RetryCalculator(retry_config)
        
        assert calculator.should_retry(1) is True
        assert calculator.should_retry(5) is False  # At max
        assert calculator.should_retry(6) is False  # Over max
    
    def test_should_retry_status_codes(self, retry_config):
        """Test retry decision based on status codes"""
        calculator = RetryCalculator(retry_config)
        
        assert calculator.should_retry(1, status_code=500) is True
        assert calculator.should_retry(1, status_code=200) is False  # Not a retryable code


# WebhookRetryQueue Tests
class TestWebhookRetryQueue:
    """Tests for WebhookRetryQueue"""
    
    def test_queue_initialization(self, retry_config):
        """Test queue initializes correctly"""
        queue = WebhookRetryQueue(retry_config)
        assert queue.size() == 0
    
    def test_enqueue(self, retry_config):
        """Test adding to retry queue"""
        queue = WebhookRetryQueue(retry_config)
        
        state = queue.enqueue(
            webhook_id="webhook-1",
            endpoint_id="endpoint-1",
            payload={"test": "data"},
            error="Connection failed"
        )
        
        assert state.attempt == 1
        assert queue.size() == 1
    
    def test_dequeue(self, retry_config):
        """Test removing from retry queue"""
        queue = WebhookRetryQueue(retry_config)
        
        queue.enqueue(
            webhook_id="webhook-1",
            endpoint_id="endpoint-1",
            payload={"test": "data"}
        )
        
        item = queue.dequeue("webhook-1")
        
        assert item is not None
        assert item["webhook_id"] == "webhook-1"
        assert queue.size() == 0
    
    def test_get_ready_retries(self, retry_config):
        """Test getting ready retries"""
        queue = WebhookRetryQueue(retry_config)
        
        queue.enqueue(
            webhook_id="webhook-1",
            endpoint_id="endpoint-1",
            payload={"test": "data"}
        )
        
        ready = queue.get_ready_retries()
        
        # Items with scheduled_for in the past should be ready
        assert isinstance(ready, list)


# EventType Tests
class TestEventType:
    """Tests for EventType enum"""
    
    def test_event_types_exist(self):
        """Test event types are defined"""
        assert EventType.TICKET_CREATED.value == "ticket.created"
        assert EventType.TICKET_UPDATED.value == "ticket.updated"
        assert EventType.MESSAGE_RECEIVED.value == "message.received"
        assert EventType.AI_RESPONSE_GENERATED.value == "ai.response.generated"


# Integration Tests
class TestWebhookIntegration:
    """Integration tests for webhook management"""
    
    @pytest.mark.asyncio
    async def test_full_webhook_flow(self, webhook_manager):
        """Test full webhook registration and trigger flow"""
        # Register webhook
        endpoint = webhook_manager.register_webhook(
            name="test_integration",
            url="https://example.com/webhook",
            events=["ticket.created"]
        )
        
        assert endpoint is not None
        assert endpoint.status == WebhookStatus.ACTIVE
        
        # Trigger event
        deliveries = await webhook_manager.trigger_event(
            event_type="ticket.created",
            payload={"ticket_id": "123"}
        )
        
        assert isinstance(deliveries, list)
    
    def test_signature_roundtrip(self, webhook_signer):
        """Test signature roundtrip"""
        secret = "test_secret"
        payload = {"ticket_id": "123", "event": "created"}
        
        # Sign
        signature = webhook_signer.sign(secret, payload, include_timestamp=True)
        
        # Verify
        result = webhook_signer.verify(secret, payload, signature)
        
        assert result.valid is True
