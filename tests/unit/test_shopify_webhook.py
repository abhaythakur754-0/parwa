"""
Unit tests for Shopify Webhook Handler.
Uses mocked database sessions - no Docker required.
"""
import os
import json
import hmac
import hashlib
import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32_characters!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")


def generate_shopify_signature(body: bytes, secret: str) -> str:
    """Generate valid Shopify HMAC signature (base64 encoded)."""
    signature = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256
    ).digest()
    return base64.b64encode(signature).decode("utf-8")


class TestShopifyRouter:
    """Tests for Shopify webhook router configuration."""

    def test_router_prefix(self):
        """Test that router has correct prefix."""
        from backend.api.webhooks.shopify import router
        assert router.prefix == "/webhooks/shopify"

    def test_router_tags(self):
        """Test that router has correct tags."""
        from backend.api.webhooks.shopify import router
        assert "Webhooks - Shopify" in router.tags


class TestOrderCreatedWebhook:
    """Tests for orders/create webhook."""

    def test_order_created_missing_signature(self):
        """Test that webhook rejects request without signature."""
        from backend.api.webhooks.shopify import router
        app = FastAPI()
        app.include_router(router)

        with TestClient(app) as client:
            response = client.post(
                "/webhooks/shopify/orders/create",
                json={"id": 12345, "order_number": 1001}
            )

        assert response.status_code == 401

    def test_order_created_invalid_signature(self):
        """Test that webhook rejects request with invalid signature."""
        from backend.api.webhooks.shopify import router
        app = FastAPI()
        app.include_router(router)

        with TestClient(app) as client:
            response = client.post(
                "/webhooks/shopify/orders/create",
                json={"id": 12345, "order_number": 1001},
                headers={"X-Shopify-Hmac-SHA256": "invalid_signature"}
            )

        assert response.status_code == 401


class TestCustomerCreatedWebhook:
    """Tests for customers/create webhook."""

    def test_customer_created_missing_signature(self):
        """Test that webhook rejects request without signature."""
        from backend.api.webhooks.shopify import router
        app = FastAPI()
        app.include_router(router)

        with TestClient(app) as client:
            response = client.post(
                "/webhooks/shopify/customers/create",
                json={"id": 12345, "email": "test@example.com"}
            )

        assert response.status_code == 401


class TestProductUpdatedWebhook:
    """Tests for products/update webhook."""

    def test_product_updated_missing_signature(self):
        """Test that webhook rejects request without signature."""
        from backend.api.webhooks.shopify import router
        app = FastAPI()
        app.include_router(router)

        with TestClient(app) as client:
            response = client.post(
                "/webhooks/shopify/products/update",
                json={"id": 12345, "title": "Test Product"}
            )

        assert response.status_code == 401


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check(self):
        """Test health check endpoint returns healthy status."""
        from backend.api.webhooks.shopify import router
        app = FastAPI()
        app.include_router(router)

        with TestClient(app) as client:
            response = client.get("/webhooks/shopify/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "shopify-webhooks"


class TestVerifyShopifyWebhook:
    """Tests for HMAC verification function."""

    def test_verify_with_no_signature(self):
        """Test verification fails with no signature."""
        from backend.api.webhooks.shopify import verify_shopify_webhook

        with patch("backend.api.webhooks.shopify.get_shopify_webhook_secret", return_value="test"):
            result = verify_shopify_webhook(b"test data", "")
            assert result is False

    def test_verify_with_no_secret(self):
        """Test verification fails when secret not configured."""
        from backend.api.webhooks.shopify import verify_shopify_webhook

        with patch("backend.api.webhooks.shopify.get_shopify_webhook_secret", return_value=None):
            result = verify_shopify_webhook(b"test data", "some_signature")
            assert result is False

    def test_verify_with_valid_base64_signature(self):
        """Test verification succeeds with valid base64 signature."""
        from backend.api.webhooks.shopify import verify_shopify_webhook

        secret = "test_secret"
        body = b'{"test": "data"}'
        signature = generate_shopify_signature(body, secret)

        with patch("backend.api.webhooks.shopify.get_shopify_webhook_secret", return_value=secret):
            result = verify_shopify_webhook(body, signature)
            assert result is True

    def test_verify_with_invalid_signature(self):
        """Test verification fails with invalid signature."""
        from backend.api.webhooks.shopify import verify_shopify_webhook

        with patch("backend.api.webhooks.shopify.get_shopify_webhook_secret", return_value="test_secret"):
            result = verify_shopify_webhook(b"test data", "invalid_signature")
            assert result is False


class TestWebhookResponse:
    """Tests for WebhookResponse schema."""

    def test_webhook_response_defaults(self):
        """Test WebhookResponse has correct defaults."""
        from backend.api.webhooks.shopify import WebhookResponse

        response = WebhookResponse(status="accepted", message="Test")
        assert response.status == "accepted"
        assert response.message == "Test"
        assert response.event_type is None
        assert response.shopify_order_id is None

    def test_webhook_response_with_all_fields(self):
        """Test WebhookResponse with all fields."""
        from backend.api.webhooks.shopify import WebhookResponse
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        response = WebhookResponse(
            status="accepted",
            message="Order processed",
            processed_at=now,
            event_type="orders/create",
            shopify_order_id=12345
        )
        assert response.status == "accepted"
        assert response.event_type == "orders/create"
        assert response.shopify_order_id == 12345
