"""Tests for Webhook Core System"""
import pytest
from datetime import datetime, timedelta
from enterprise.webhooks.webhook_core import (
    WebhookManager, Webhook, WebhookStatus, WebhookEvent
)
from enterprise.webhooks.webhook_signer import WebhookSigner
from enterprise.webhooks.webhook_validator import WebhookValidator

class TestWebhookManager:
    @pytest.fixture
    def manager(self):
        return WebhookManager()

    def test_create_webhook(self, manager):
        webhook = manager.create_webhook("tenant_001", "Test Webhook", "https://example.com/webhook", {"ticket.created"})
        assert webhook.webhook_id is not None
        assert webhook.status == WebhookStatus.ACTIVE

    def test_get_webhook(self, manager):
        created = manager.create_webhook("tenant_001", "Test", "https://example.com/webhook", {"*"})
        webhook = manager.get_webhook(created.webhook_id)
        assert webhook is not None

    def test_get_tenant_webhooks(self, manager):
        manager.create_webhook("tenant_001", "WH1", "https://example.com/wh1", {"*"})
        manager.create_webhook("tenant_001", "WH2", "https://example.com/wh2", {"*"})
        webhooks = manager.get_tenant_webhooks("tenant_001")
        assert len(webhooks) == 2

    def test_delete_webhook(self, manager):
        webhook = manager.create_webhook("tenant_001", "Test", "https://example.com/webhook", {"*"})
        result = manager.delete_webhook(webhook.webhook_id)
        assert result is True
        assert manager.get_webhook(webhook.webhook_id) is None

    def test_pause_webhook(self, manager):
        webhook = manager.create_webhook("tenant_001", "Test", "https://example.com/webhook", {"*"})
        manager.pause_webhook(webhook.webhook_id)
        assert manager.get_webhook(webhook.webhook_id).status == WebhookStatus.PAUSED

    def test_activate_webhook(self, manager):
        webhook = manager.create_webhook("tenant_001", "Test", "https://example.com/webhook", {"*"})
        manager.pause_webhook(webhook.webhook_id)
        manager.activate_webhook(webhook.webhook_id)
        assert manager.get_webhook(webhook.webhook_id).status == WebhookStatus.ACTIVE

    def test_record_trigger(self, manager):
        webhook = manager.create_webhook("tenant_001", "Test", "https://example.com/webhook", {"*"})
        manager.record_trigger(webhook.webhook_id, True)
        manager.record_trigger(webhook.webhook_id, False)
        updated = manager.get_webhook(webhook.webhook_id)
        assert updated.success_count == 1
        assert updated.failure_count == 1

    def test_get_webhooks_for_event(self, manager):
        manager.create_webhook("tenant_001", "WH1", "https://example.com/wh1", {"ticket.created"})
        manager.create_webhook("tenant_001", "WH2", "https://example.com/wh2", {"*"})
        webhooks = manager.get_webhooks_for_event("ticket.created", "tenant_001")
        assert len(webhooks) == 2

    def test_invalid_url(self, manager):
        with pytest.raises(ValueError):
            manager.create_webhook("tenant_001", "Test", "invalid-url", {"*"})

    def test_get_metrics(self, manager):
        manager.create_webhook("tenant_001", "Test", "https://example.com/webhook", {"*"})
        metrics = manager.get_metrics()
        assert metrics["total_webhooks"] == 1


class TestWebhookSigner:
    @pytest.fixture
    def signer(self):
        return WebhookSigner()

    def test_sign_payload(self, signer):
        payload = {"event": "test", "data": {"id": 123}}
        secret = "test_secret"
        signature = signer.sign(payload, secret)
        assert signature.startswith("t=")
        assert "v1=" in signature

    def test_verify_signature(self, signer):
        payload = {"event": "test", "data": {"id": 123}}
        secret = "test_secret"
        signature = signer.sign(payload, secret)
        assert signer.verify(payload, secret, signature) is True

    def test_verify_wrong_secret(self, signer):
        payload = {"event": "test", "data": {"id": 123}}
        signature = signer.sign(payload, "correct_secret")
        assert signer.verify(payload, "wrong_secret", signature) is False

    def test_verify_modified_payload(self, signer):
        payload = {"event": "test", "data": {"id": 123}}
        signature = signer.sign(payload, "secret")
        modified_payload = {"event": "test", "data": {"id": 456}}
        assert signer.verify(modified_payload, "secret", signature) is False

    def test_create_signed_payload(self, signer):
        signed = signer.create_signed_payload("ticket.created", {"id": 1}, "secret")
        assert "event" in signed
        assert "signature" in signed


class TestWebhookValidator:
    @pytest.fixture
    def validator(self):
        return WebhookValidator()

    def test_validate_valid_url(self, validator):
        result = validator.validate_url("https://example.com/webhook")
        assert result.valid is True

    def test_validate_invalid_url(self, validator):
        result = validator.validate_url("invalid-url")
        assert result.valid is False

    def test_validate_http_url(self, validator):
        result = validator.validate_url("http://example.com/webhook")
        assert result.valid is False

    def test_validate_localhost(self, validator):
        result = validator.validate_url("https://localhost/webhook")
        assert result.valid is False

    def test_validate_private_ip(self, validator):
        result = validator.validate_url("https://192.168.1.1/webhook")
        assert result.valid is False

    def test_validate_payload(self, validator):
        result = validator.validate_payload({"test": "data"})
        assert result.valid is True

    def test_validate_events(self, validator):
        allowed = ["ticket.created", "ticket.updated"]
        result = validator.validate_events(["ticket.created"], allowed)
        assert result.valid is True

    def test_validate_invalid_events(self, validator):
        allowed = ["ticket.created", "ticket.updated"]
        result = validator.validate_events(["invalid.event"], allowed)
        assert result.valid is False

    def test_validate_headers(self, validator):
        result = validator.validate_headers({"X-Custom": "value"})
        assert result.valid is True


class TestWebhook:
    def test_success_rate_no_triggers(self):
        webhook = Webhook(webhook_id="wh_001", tenant_id="t1", name="Test", url="https://example.com", secret="s")
        assert webhook.success_rate == 100.0

    def test_success_rate_with_triggers(self):
        webhook = Webhook(webhook_id="wh_001", tenant_id="t1", name="Test", url="https://example.com", secret="s", success_count=8, failure_count=2)
        assert webhook.success_rate == 80.0

    def test_total_triggers(self):
        webhook = Webhook(webhook_id="wh_001", tenant_id="t1", name="Test", url="https://example.com", secret="s", success_count=5, failure_count=3)
        assert webhook.total_triggers == 8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
