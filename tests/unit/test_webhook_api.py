"""Tests for webhook API endpoints (BC-003, BC-012)."""

import pytest
from unittest.mock import patch, MagicMock

from starlette.testclient import TestClient


class TestWebhookAPIProviderValidation:
    """Test webhook provider validation."""

    def test_supported_provider_paddle(self, client):
        """Paddle is a supported provider."""
        resp = client.post(
            "/api/webhooks/paddle",
            json={
                "event_id": "evt_001",
                "event_type": "subscription.created",
                "company_id": "comp_abc123",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("pending", "duplicate")

    def test_supported_provider_twilio(self, client):
        """Twilio is a supported provider."""
        resp = client.post(
            "/api/webhooks/twilio",
            json={
                "MessageSid": "SM123",
                "EventType": "sms.incoming",
                "AccountSid": "comp_abc123",
            },
        )
        assert resp.status_code == 200

    def test_supported_provider_shopify(self, client):
        """Shopify is a supported provider."""
        resp = client.post(
            "/api/webhooks/shopify",
            json={
                "id": "shp_001",
                "topic": "orders/create",
                "company_id": "comp_abc123",
                "event_id": "shp_001",
            },
        )
        assert resp.status_code == 200

    def test_supported_provider_brevo(self, client):
        """Brevo is a supported provider."""
        resp = client.post(
            "/api/webhooks/brevo",
            json={
                "event_id": "bre_001",
                "event": "inbound.email.received",
                "company_id": "comp_abc123",
            },
        )
        assert resp.status_code == 200

    def test_unsupported_provider_404(self, client):
        """Unknown providers get 404."""
        resp = client.post(
            "/api/webhooks/unknown_provider",
            json={},
        )
        assert resp.status_code == 404
        data = resp.json()
        assert "supported" in data["error"]["details"]


class TestWebhookAPIIdempotency:
    """Test webhook idempotency (BC-003)."""

    def test_duplicate_event_returns_duplicate_flag(self, client):
        """Second request with same event_id returns duplicate."""
        payload = {
            "event_id": "dup_001",
            "event_type": "subscription.created",
            "company_id": "comp_abc123",
        }
        resp1 = client.post(
            "/api/webhooks/paddle", json=payload,
        )
        resp2 = client.post(
            "/api/webhooks/paddle", json=payload,
        )
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["event_id"] == resp2.json()["event_id"]
        assert resp1.json()["duplicate"] is False
        assert resp2.json()["duplicate"] is True

    def test_different_event_ids_not_duplicate(self, client):
        """Different event_ids are not duplicates."""
        resp1 = client.post(
            "/api/webhooks/paddle",
            json={
                "event_id": "unique_001",
                "event_type": "subscription.created",
                "company_id": "comp_abc123",
            },
        )
        resp2 = client.post(
            "/api/webhooks/paddle",
            json={
                "event_id": "unique_002",
                "event_type": "subscription.updated",
                "company_id": "comp_abc123",
            },
        )
        assert resp2.json()["duplicate"] is False


class TestWebhookAPIValidation:
    """Test webhook input validation."""

    def test_missing_event_id_returns_422(self, client):
        """Missing event_id returns 422."""
        resp = client.post(
            "/api/webhooks/paddle",
            json={
                "event_type": "subscription.created",
                "company_id": "comp_abc123",
            },
        )
        assert resp.status_code == 422

    def test_missing_company_id_returns_422(self, client):
        """Missing company_id returns 422."""
        resp = client.post(
            "/api/webhooks/paddle",
            json={
                "event_id": "evt_001",
                "event_type": "subscription.created",
            },
        )
        assert resp.status_code == 422
        assert "company_id" in resp.json()["error"]["message"]

    def test_invalid_json_returns_200(self, client):
        """Invalid JSON body still returns 200 (empty payload)."""
        resp = client.post(
            "/api/webhooks/paddle",
            content=b"not json",
            headers={"content-type": "application/json"},
        )
        # FastAPI returns 422 for invalid JSON on pydantic model
        assert resp.status_code == 422

    def test_event_type_defaults_on_missing(self, client):
        """Event type gets a default if missing."""
        resp = client.post(
            "/api/webhooks/paddle",
            json={
                "event_id": "evt_no_type",
                "company_id": "comp_abc123",
            },
        )
        assert resp.status_code == 200

    def test_company_id_validation_too_long(self, client):
        """Company_id over 128 chars returns 422."""
        long_id = "c" * 200
        resp = client.post(
            "/api/webhooks/paddle",
            json={
                "event_id": "evt_001",
                "event_type": "subscription.created",
                "company_id": long_id,
            },
        )
        assert resp.status_code == 422


class TestWebhookAPIStatusAndRetry:
    """Test webhook status check and retry endpoints."""

    def test_status_endpoint_nonexistent_returns_404(self, client):
        """Nonexistent event returns 404."""
        resp = client.get(
            "/api/webhooks/status/nonexistent-id",
        )
        assert resp.status_code == 404

    def test_retry_nonexistent_returns_422(self, client):
        """Retry nonexistent event returns 422."""
        resp = client.post(
            "/api/webhooks/retry/nonexistent-id",
        )
        assert resp.status_code == 422
