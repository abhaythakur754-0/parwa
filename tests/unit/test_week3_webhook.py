"""
Week 3 Unit Tests — Webhook Framework (BC-003, BC-011)

Tests for:
- webhook API endpoints: receive_webhook, get_webhook_status, retry_webhook
- HMAC verification: paddle, twilio, shopify, brevo
- Helper functions: _get_company_id, _get_event_id, _get_event_type
"""

import sys
import os
import hashlib
import hmac
import json
import pytest
import base64
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))


# ── Helper function tests ───────────────────────────────────────

class TestGetCompanyIDFromPayload:

    def setup_method(self):
        from backend.app.api.webhooks import _get_company_id_from_payload
        self.fn = _get_company_id_from_payload

    def test_paddle_custom_data(self):
        payload = {"custom_data": {"company_id": "acme"}}
        assert self.fn("paddle", payload) == "acme"

    def test_paddle_toplevel(self):
        payload = {"company_id": "acme"}
        assert self.fn("paddle", payload) == "acme"

    def test_shopify_x_header(self):
        payload = {"x_company_id": "shop1"}
        assert self.fn("shopify", payload) == "shop1"

    def test_shopify_toplevel(self):
        payload = {"company_id": "shop1"}
        assert self.fn("shopify", payload) == "shop1"

    def test_twilio_account_sid(self):
        payload = {"AccountSid": "AC123"}
        assert self.fn("twilio", payload) == "AC123"

    def test_brevo_company_id(self):
        payload = {"company_id": "brevo1"}
        assert self.fn("brevo", payload) == "brevo1"

    def test_unknown_fallback(self):
        payload = {"company_id": "unknown1"}
        assert self.fn("unknown_provider", payload) == "unknown1"

    def test_missing_returns_none(self):
        assert self.fn("paddle", {}) is None


class TestGetEventIDFromPayload:

    def setup_method(self):
        from backend.app.api.webhooks import _get_event_id_from_payload
        self.fn = _get_event_id_from_payload

    def test_paddle_event_id(self):
        assert self.fn("paddle", {"event_id": "evt_123"}) == "evt_123"

    def test_shopify_id(self):
        assert self.fn("shopify", {"id": "gid://123"}) == "gid://123"

    def test_twilio_message_sid(self):
        assert self.fn("twilio", {"MessageSid": "SM123"}) == "SM123"

    def test_twilio_call_sid_fallback(self):
        assert self.fn("twilio", {"CallSid": "CA123"}) == "CA123"

    def test_brevo_event_id(self):
        assert self.fn("brevo", {"event_id": "b_123"}) == "b_123"

    def test_missing_returns_none(self):
        assert self.fn("paddle", {}) is None


class TestGetEventTypeFromPayload:

    def setup_method(self):
        from backend.app.api.webhooks import _get_event_type_from_payload
        self.fn = _get_event_type_from_payload

    def test_paddle_event_type(self):
        assert self.fn("paddle", {"event_type": "subscription.created"}) == "subscription.created"

    def test_shopify_topic(self):
        assert self.fn("shopify", {"topic": "orders/create"}) == "orders/create"

    def test_twilio_event_type(self):
        assert self.fn("twilio", {"EventType": "sms.incoming"}) == "sms.incoming"

    def test_twilio_default(self):
        assert self.fn("twilio", {}) == "sms.incoming"

    def test_brevo_hard_bounce(self):
        assert self.fn("brevo", {"event": "hard_bounce"}) == "bounce"

    def test_brevo_spam(self):
        assert self.fn("brevo", {"event": "spam"}) == "complaint"

    def test_brevo_unknown_passthrough(self):
        assert self.fn("brevo", {"event": "delivered"}) == "delivered"

    def test_unknown_fallback(self):
        assert self.fn("other", {"event_type": "custom.event"}) == "custom.event"


# ── HMAC Verification Tests ─────────────────────────────────────

class TestPaddleHMAC:

    def test_valid_signature(self):
        from backend.app.security.hmac_verification import verify_paddle_signature
        secret = "test_secret_123"
        body = b'{"event_id": "evt_1"}'
        ts = str(int(time.time()))
        payload = f"{ts}:{body.decode()}".encode()
        sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        signature = f"ts={ts};h1={sig}"
        assert verify_paddle_signature(body, signature, secret) is True

    def test_invalid_signature(self):
        from backend.app.security.hmac_verification import verify_paddle_signature
        secret = "test_secret_123"
        body = b'{"event_id": "evt_1"}'
        assert verify_paddle_signature(body, "ts=123;h1=invalid", secret) is False

    def test_tampered_body(self):
        from backend.app.security.hmac_verification import verify_paddle_signature
        secret = "test_secret_123"
        body = b'{"event_id": "evt_1"}'
        ts = str(int(time.time()))
        payload = f"{ts}:{body.decode()}".encode()
        sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        signature = f"ts={ts};h1={sig}"
        tampered = b'{"event_id": "evt_2"}'
        assert verify_paddle_signature(tampered, signature, secret) is False

    def test_empty_signature(self):
        from backend.app.security.hmac_verification import verify_paddle_signature
        assert verify_paddle_signature(b'{}', "", "secret") is False


class TestShopifyHMAC:

    def test_valid_signature(self):
        from backend.app.security.hmac_verification import verify_shopify_hmac
        secret = "shopify_secret"
        body = b'{"id": 123}'
        sig = hmac.new(secret.encode(), body, hashlib.sha256).digest()
        signature = base64.b64encode(sig).decode()
        assert verify_shopify_hmac(body, signature, secret) is True

    def test_invalid_signature(self):
        from backend.app.security.hmac_verification import verify_shopify_hmac
        assert verify_shopify_hmac(b'{}', "invalid_sig", "secret") is False


class TestBrevoIPVerification:

    def test_ip_in_range(self):
        from backend.app.security.hmac_verification import verify_brevo_ip
        assert verify_brevo_ip("1.2.3.4", allowed_ips=["1.2.3.0/24"]) is True

    def test_ip_out_of_range(self):
        from backend.app.security.hmac_verification import verify_brevo_ip
        assert verify_brevo_ip("10.0.0.1", allowed_ips=["1.2.3.0/24"]) is False

    def test_no_allowed_ips(self):
        from backend.app.security.hmac_verification import verify_brevo_ip
        # Default IPs should be used
        result = verify_brevo_ip("1.2.3.4")
        # May or may not match defaults, just test it doesn't crash
        assert isinstance(result, bool)


# ── Webhook API Tests ──────────────────────────────────────────

class TestReceiveWebhook:

    @pytest.mark.asyncio
    async def test_unsupported_provider_404(self):
        from backend.app.api.webhooks import receive_webhook
        from fastapi import Request
        mock_request = MagicMock(spec=Request)
        mock_request.url = MagicMock()
        mock_request.url.path = "/api/webhooks/unknown"
        result = await receive_webhook("unknown", mock_request)
        assert result.status_code == 404

    @pytest.mark.asyncio
    async def test_missing_timestamp_rejected(self):
        from backend.app.api.webhooks import receive_webhook
        mock_request = MagicMock()
        mock_request.body = AsyncMock(return_value=b'{"event_id":"e1","event_type":"t1","company_id":"c1"}')
        mock_request.json = AsyncMock(return_value={"event_id": "e1", "event_type": "t1", "company_id": "c1"})
        mock_request.headers = {}
        result = await receive_webhook("paddle", mock_request)
        assert result.status_code == 403  # REPLAY_DETECTED

    @pytest.mark.asyncio
    async def test_old_timestamp_rejected(self):
        from backend.app.api.webhooks import receive_webhook
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        payload = {"event_id": "e1", "event_type": "t1", "company_id": "c1", "timestamp": old_time}
        mock_request = MagicMock()
        mock_request.body = AsyncMock(return_value=json.dumps(payload).encode())
        mock_request.json = AsyncMock(return_value=payload)
        mock_request.headers = {}
        result = await receive_webhook("paddle", mock_request)
        assert result.status_code == 403  # REPLAY_DETECTED

    @pytest.mark.asyncio
    async def test_missing_event_id_422(self):
        from backend.app.api.webhooks import receive_webhook
        fresh_time = datetime.now(timezone.utc).isoformat()
        payload = {"event_type": "t1", "company_id": "c1", "timestamp": fresh_time}
        mock_request = MagicMock()
        mock_request.body = AsyncMock(return_value=json.dumps(payload).encode())
        mock_request.json = AsyncMock(return_value=payload)
        mock_request.headers = {}
        result = await receive_webhook("paddle", mock_request)
        assert result.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_company_id_422(self):
        from backend.app.api.webhooks import receive_webhook
        fresh_time = datetime.now(timezone.utc).isoformat()
        payload = {"event_id": "e1", "event_type": "t1", "timestamp": fresh_time}
        mock_request = MagicMock()
        mock_request.body = AsyncMock(return_value=json.dumps(payload).encode())
        mock_request.json = AsyncMock(return_value=payload)
        mock_request.headers = {}
        result = await receive_webhook("paddle", mock_request)
        assert result.status_code == 422

    @pytest.mark.asyncio
    async def test_payload_too_large_413(self):
        from backend.app.api.webhooks import receive_webhook, MAX_WEBHOOK_PAYLOAD_SIZE
        big_body = b"x" * (MAX_WEBHOOK_PAYLOAD_SIZE + 1)
        mock_request = MagicMock()
        mock_request.body = AsyncMock(return_value=big_body)
        mock_request.json = AsyncMock(side_effect=Exception("too big"))
        mock_request.headers = {}
        result = await receive_webhook("paddle", mock_request)
        assert result.status_code == 413

    @pytest.mark.asyncio
    async def test_missing_secret_500(self):
        """H-07: Fail-closed when secret is not configured."""
        from backend.app.api.webhooks import receive_webhook
        fresh_time = datetime.now(timezone.utc).isoformat()
        payload = {"event_id": "e1", "event_type": "t1", "company_id": "c1", "timestamp": fresh_time}
        mock_request = MagicMock()
        mock_request.body = AsyncMock(return_value=json.dumps(payload).encode())
        mock_request.json = AsyncMock(return_value=payload)
        mock_request.headers = {"paddle-signature": "ts=123;h1=abc"}
        mock_settings = MagicMock()
        mock_settings.PADDLE_WEBHOOK_SECRET = ""
        with patch("backend.app.api.webhooks._get_settings", return_value=mock_settings):
            result = await receive_webhook("paddle", mock_request)
            assert result.status_code == 500
            assert "CONFIGURATION_ERROR" in json.loads(result.body)["error"]["code"]


class TestCheckProviderSecretConfigured:

    def test_paddle_secret_set(self):
        from backend.app.api.webhooks import _check_provider_secret_configured
        mock_settings = MagicMock()
        mock_settings.PADDLE_WEBHOOK_SECRET = "secret123"
        assert _check_provider_secret_configured("paddle", mock_settings) is None

    def test_paddle_secret_missing(self):
        from backend.app.api.webhooks import _check_provider_secret_configured
        mock_settings = MagicMock()
        mock_settings.PADDLE_WEBHOOK_SECRET = ""
        result = _check_provider_secret_configured("paddle", mock_settings)
        assert result is not None
        assert "PADDLE_WEBHOOK_SECRET" in result

    def test_shopify_secret_missing(self):
        from backend.app.api.webhooks import _check_provider_secret_configured
        mock_settings = MagicMock()
        mock_settings.SHOPIFY_WEBHOOK_SECRET = ""
        result = _check_provider_secret_configured("shopify", mock_settings)
        assert "SHOPIFY_WEBHOOK_SECRET" in result

    def test_twilio_secret_missing(self):
        from backend.app.api.webhooks import _check_provider_secret_configured
        mock_settings = MagicMock()
        mock_settings.TWILIO_AUTH_TOKEN = ""
        result = _check_provider_secret_configured("twilio", mock_settings)
        assert "TWILIO_AUTH_TOKEN" in result
