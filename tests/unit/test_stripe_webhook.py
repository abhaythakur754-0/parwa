"""
Unit tests for Stripe Webhook Handler.
Uses mocked database sessions - no Docker required.
"""
import os
import json
import hmac
import hashlib
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_unit_tests_32_characters!")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")


def create_test_app():
    """Create a FastAPI test app with stripe webhook router."""
    app = FastAPI()

    async def override_get_db():
        return AsyncMock()

    from backend.app.dependencies import get_db
    app.dependency_overrides[get_db] = override_get_db

    from backend.api.webhooks.stripe import router
    app.include_router(router)

    return app


def generate_stripe_signature(body: bytes, secret: str) -> str:
    """Generate valid Stripe signature format."""
    timestamp = str(int(time.time()))
    signed_payload = f"{timestamp}.{body.decode()}"
    signature = hmac.new(
        secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    
    return f"t={timestamp},v1={signature}"


class TestStripeRouter:
    """Tests for Stripe webhook router configuration."""

    def test_router_prefix(self):
        """Test that router has correct prefix."""
        from backend.api.webhooks.stripe import router
        assert router.prefix == "/webhooks/stripe"

    def test_router_tags(self):
        """Test that router has correct tags."""
        from backend.api.webhooks.stripe import router
        assert "Webhooks - Stripe" in router.tags


class TestWebhookAuthentication:
    """Tests for webhook authentication."""

    def test_webhook_missing_signature(self):
        """Test that webhook rejects request without signature."""
        app = create_test_app()

        payload = {
            "id": "evt_test123",
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_test123"}}
        }

        with TestClient(app) as client:
            response = client.post(
                "/webhooks/stripe",
                json=payload
            )

        assert response.status_code == 401

    def test_webhook_invalid_signature(self):
        """Test that webhook rejects request with invalid signature."""
        app = create_test_app()

        payload = {
            "id": "evt_test123",
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_test123"}}
        }

        with TestClient(app) as client:
            response = client.post(
                "/webhooks/stripe",
                json=payload,
                headers={"Stripe-Signature": "invalid_signature"}
            )

        assert response.status_code == 401

    def test_webhook_missing_v1_in_signature(self):
        """Test that webhook rejects signature without v1 component."""
        app = create_test_app()

        payload = {
            "id": "evt_test123",
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_test123"}}
        }

        with TestClient(app) as client:
            response = client.post(
                "/webhooks/stripe",
                json=payload,
                headers={"Stripe-Signature": "t=1234567890"}
            )

        assert response.status_code == 401


class TestPaymentSucceeded:
    """Tests for payment_intent.succeeded event."""

    def test_payment_succeeded_missing_signature(self):
        """Test payment succeeded without signature."""
        app = create_test_app()

        payload = {
            "id": "evt_test123",
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_test123", "amount": 1000}}
        }

        with TestClient(app) as client:
            response = client.post(
                "/webhooks/stripe",
                json=payload
            )

        assert response.status_code == 401


class TestRefundWebhook:
    """Tests for charge.refunded event."""

    def test_refund_missing_signature(self):
        """Test refund without signature."""
        app = create_test_app()

        payload = {
            "id": "evt_test123",
            "type": "charge.refunded",
            "data": {"object": {"id": "ch_test123", "amount_refunded": 500}}
        }

        with TestClient(app) as client:
            response = client.post(
                "/webhooks/stripe",
                json=payload
            )

        assert response.status_code == 401


class TestInvoicePaid:
    """Tests for invoice.paid event."""

    def test_invoice_paid_missing_signature(self):
        """Test invoice paid without signature."""
        app = create_test_app()

        payload = {
            "id": "evt_test123",
            "type": "invoice.paid",
            "data": {"object": {"id": "in_test123", "amount_paid": 2500}}
        }

        with TestClient(app) as client:
            response = client.post(
                "/webhooks/stripe",
                json=payload
            )

        assert response.status_code == 401


class TestSubscriptionUpdated:
    """Tests for customer.subscription.updated event."""

    def test_subscription_updated_missing_signature(self):
        """Test subscription updated without signature."""
        app = create_test_app()

        payload = {
            "id": "evt_test123",
            "type": "customer.subscription.updated",
            "data": {"object": {"id": "sub_test123", "status": "active"}}
        }

        with TestClient(app) as client:
            response = client.post(
                "/webhooks/stripe",
                json=payload
            )

        assert response.status_code == 401


class TestUnknownEventType:
    """Tests for unknown event types."""

    def test_unknown_event_missing_signature(self):
        """Test unknown event without signature."""
        app = create_test_app()

        payload = {
            "id": "evt_test123",
            "type": "unknown.event.type",
            "data": {"object": {"id": "obj_test123"}}
        }

        with TestClient(app) as client:
            response = client.post(
                "/webhooks/stripe",
                json=payload
            )

        assert response.status_code == 401


class TestWebhookResponseSchema:
    """Tests for WebhookResponse schema."""

    def test_webhook_response_schema(self):
        """Test WebhookResponse schema creation."""
        from backend.api.webhooks.stripe import WebhookResponse
        from datetime import datetime, timezone

        response = WebhookResponse(
            status="accepted",
            message="Event processed",
            processed_at=datetime.now(timezone.utc),
            event_type="payment_intent.succeeded",
            event_id="evt_test123"
        )
        
        assert response.status == "accepted"
        assert response.message == "Event processed"
        assert response.event_type == "payment_intent.succeeded"
        assert response.event_id == "evt_test123"


class TestVerifyStripeWebhook:
    """Tests for verify_stripe_webhook function."""

    def test_verify_with_no_signature(self):
        """Test verification with no signature returns False."""
        from backend.api.webhooks.stripe import verify_stripe_webhook
        
        result = verify_stripe_webhook(b"test body", "")
        assert result is False

    def test_verify_with_no_secret_configured(self):
        """Test verification with no secret configured returns False."""
        from backend.api.webhooks.stripe import verify_stripe_webhook
        
        with patch("backend.api.webhooks.stripe.settings") as mock_settings:
            mock_settings.stripe_webhook_secret = None
            
            # Need to reimport to get mocked settings
            from backend.api.webhooks import stripe
            stripe.settings = mock_settings
            
            result = stripe.verify_stripe_webhook(b"test body", "some_signature")
            assert result is False


class TestCreatePendingApproval:
    """Tests for create_pending_approval function."""

    @pytest.mark.asyncio
    async def test_create_pending_approval_returns_uuid(self):
        """Test that create_pending_approval returns a UUID."""
        from backend.api.webhooks.stripe import create_pending_approval
        
        mock_db = AsyncMock()
        company_id = uuid.uuid4()
        
        result = await create_pending_approval(
            db=mock_db,
            company_id=company_id,
            event_type="charge.refunded",
            event_data={"test": "data"}
        )
        
        assert isinstance(result, uuid.UUID)


class TestGetCompanyByStripeAccount:
    """Tests for get_company_by_stripe_account function."""

    @pytest.mark.asyncio
    async def test_get_company_returns_none_when_no_companies(self):
        """Test that function returns None when no active companies exist."""
        from backend.api.webhooks.stripe import get_company_by_stripe_account
        
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result
        
        result = await get_company_by_stripe_account(mock_db, "acct_test123")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_company_returns_first_active(self):
        """Test that function returns first active company."""
        from backend.api.webhooks.stripe import get_company_by_stripe_account
        
        mock_db = AsyncMock()
        mock_company = MagicMock()
        mock_company.id = uuid.uuid4()
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_company]
        mock_db.execute.return_value = mock_result
        
        result = await get_company_by_stripe_account(mock_db, "acct_test123")
        
        assert result == mock_company


import uuid  # Add import at top for tests that use uuid
