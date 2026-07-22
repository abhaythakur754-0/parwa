"""
HMAC Signature Verification — Unit Tests

Tests for webhook signature verification functions.
No database connection required — pure function tests.

Run: cd /home/z/my-project/parwa && python -m pytest backend/tests/unit/test_hmac_verification.py -v
"""

import hashlib
import hmac
import os
import sys
import time

import pytest

# Ensure backend/app is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.security.hmac_verification import (
    verify_paddle_signature,
    verify_twilio_signature,
    verify_shopify_hmac,
    verify_brevo_ip,
    _verify_webhook_timestamp,
    _WEBHOOK_FRESHNESS_SECONDS,
    DEFAULT_BREVO_IPS,
)


# ═══════════════════════════════════════════════════════════════════
# verify_paddle_signature
# ═══════════════════════════════════════════════════════════════════


class TestVerifyPaddleSignature:
    """Tests for Paddle HMAC-SHA256 verification."""

    def test_valid_signature(self):
        """Correct HMAC should pass verification."""
        body = b'{"event_id": "evt_123"}'
        secret = "paddle_test_secret"
        expected = hmac.new(
            secret.encode(), body, hashlib.sha256,
        ).hexdigest()
        assert verify_paddle_signature(body, expected, secret)

    def test_invalid_signature(self):
        """Wrong HMAC should fail verification."""
        body = b'{"event_id": "evt_123"}'
        secret = "paddle_test_secret"
        assert not verify_paddle_signature(body, "wrong_sig", secret)

    def test_empty_secret_rejects(self):
        """Empty secret should fail (fail-closed)."""
        body = b'{"event_id": "evt_123"}'
        sig = "somesig"
        assert not verify_paddle_signature(body, sig, "")

    def test_empty_body_rejects(self):
        """Empty body should fail."""
        assert not verify_paddle_signature(b"", "sig", "secret")

    def test_empty_signature_rejects(self):
        """Empty signature should fail."""
        assert not verify_paddle_signature(b"body", "", "secret")

    def test_none_inputs_reject(self):
        """None inputs should not crash and return False."""
        assert not verify_paddle_signature(None, "sig", "secret")
        assert not verify_paddle_signature(b"body", None, "secret")
        assert not verify_paddle_signature(b"body", "sig", None)

    def test_signature_with_whitespace(self):
        """Signature with leading/trailing whitespace should still work."""
        body = b"test_payload"
        secret = "my_secret"
        expected = hmac.new(
            secret.encode(), body, hashlib.sha256,
        ).hexdigest()
        # Add whitespace — the function strips it
        assert verify_paddle_signature(body, f"  {expected}  ", secret)


# ═══════════════════════════════════════════════════════════════════
# verify_twilio_signature
# ═══════════════════════════════════════════════════════════════════


class TestVerifyTwilioSignature:
    """Tests for Twilio RFC 5849 signature verification."""

    def test_valid_signature(self):
        """Correct Twilio signature should pass."""
        url = "https://api.parwa.io/api/webhooks/twilio"
        params = {"AccountSid": "AC123", "Body": "hello"}
        auth_token = "twilio_test_token"
        sorted_params = sorted(params.items())
        data = url
        for key, value in sorted_params:
            data += key + str(value)
        expected = hmac.new(
            auth_token.encode(), data.encode(), hashlib.sha1,
        ).hexdigest()
        assert verify_twilio_signature(
            url, params, expected, auth_token,
        )

    def test_invalid_signature(self):
        """Wrong signature should fail."""
        assert not verify_twilio_signature(
            "https://api.parwa.io/webhook",
            {"key": "val"}, "wrong_sig", "token",
        )

    def test_empty_auth_token_rejects(self):
        """Empty auth token should fail (fail-closed)."""
        assert not verify_twilio_signature(
            "https://api.parwa.io/webhook",
            {"key": "val"}, "sig", "",
        )

    def test_empty_url_rejects(self):
        """Empty URL should fail."""
        assert not verify_twilio_signature(
            "", {"key": "val"}, "sig", "token",
        )

    def test_empty_params_rejects(self):
        """Empty params dict should fail."""
        assert not verify_twilio_signature(
            "https://api.parwa.io/webhook", {}, "sig", "token",
        )

    def test_param_order_doesnt_matter(self):
        """Parameter order should not affect signature (sorted)."""
        url = "https://api.parwa.io/webhook"
        auth_token = "token"
        params1 = {"b": "2", "a": "1"}
        params2 = {"a": "1", "b": "2"}
        sorted_params = sorted(params1.items())
        data = url
        for key, value in sorted_params:
            data += key + str(value)
        expected = hmac.new(
            auth_token.encode(), data.encode(), hashlib.sha1,
        ).hexdigest()
        assert verify_twilio_signature(url, params1, expected, auth_token)
        assert verify_twilio_signature(url, params2, expected, auth_token)


# ═══════════════════════════════════════════════════════════════════
# verify_shopify_hmac
# ═══════════════════════════════════════════════════════════════════


class TestVerifyShopifyHMAC:
    """Tests for Shopify HMAC-SHA256 base64 verification."""

    def test_valid_hmac(self):
        """Correct Shopify HMAC should pass."""
        body = b'{"id": "webhook_123"}'
        secret = "shopify_test_secret"
        import base64
        expected = hmac.new(
            secret.encode(), body, hashlib.sha256,
        ).digest()
        expected_b64 = base64.b64encode(expected).decode()
        assert verify_shopify_hmac(body, expected_b64, secret)

    def test_invalid_hmac(self):
        """Wrong HMAC should fail."""
        assert not verify_shopify_hmac(
            b"body", "wrong_hmac", "secret",
        )

    def test_empty_secret_rejects(self):
        """Empty secret should fail (fail-closed)."""
        assert not verify_shopify_hmac(b"body", "hmac", "")

    def test_empty_body_rejects(self):
        """Empty body should fail."""
        assert not verify_shopify_hmac(b"", "hmac", "secret")

    def test_empty_hmac_header_rejects(self):
        """Empty HMAC header should fail."""
        assert not verify_shopify_hmac(b"body", "", "secret")

    def test_none_inputs_reject(self):
        """None inputs should not crash."""
        assert not verify_shopify_hmac(None, "hmac", "secret")
        assert not verify_shopify_hmac(b"body", None, "secret")
        assert not verify_shopify_hmac(b"body", "hmac", None)


# ═══════════════════════════════════════════════════════════════════
# verify_brevo_ip
# ═══════════════════════════════════════════════════════════════════


class TestVerifyBrevoIP:
    """Tests for Brevo IP allowlist verification."""

    def test_ip_in_default_range(self):
        """IP within default Brevo range should be allowed."""
        # 185.107.232.0/24 includes .1 through .254
        assert verify_brevo_ip("185.107.232.1")

    def test_ip_in_cidr_boundary(self):
        """IP at CIDR boundary should be allowed."""
        assert verify_brevo_ip("185.107.232.254")

    def test_ip_outside_range(self):
        """IP outside Brevo ranges should be rejected."""
        assert not verify_brevo_ip("8.8.8.8")

    def test_custom_allowed_ips(self):
        """Custom IP list should override defaults."""
        assert verify_brevo_ip(
            "10.0.0.1", allowed_ips=["10.0.0.0/24"],
        )

    def test_custom_empty_list(self):
        """Empty custom IP list should block everything."""
        assert not verify_brevo_ip(
            "185.107.232.1", allowed_ips=[],
        )

    def test_empty_client_ip(self):
        """Empty client IP should fail."""
        assert not verify_brevo_ip("")
        assert not verify_brevo_ip(None)

    def test_invalid_client_ip(self):
        """Invalid IP string should not crash."""
        assert not verify_brevo_ip("not-an-ip")

    def test_invalid_cidr_in_list(self):
        """Invalid CIDR in custom list should not crash."""
        assert not verify_brevo_ip(
            "10.0.0.1", allowed_ips=["not-a-cidr"],
        )


# ═══════════════════════════════════════════════════════════════════
# _verify_webhook_timestamp
# ═══════════════════════════════════════════════════════════════════


class TestVerifyWebhookTimestamp:
    """Tests for webhook timestamp freshness validation."""

    def test_current_timestamp_passes(self):
        """Timestamp close to now should pass."""
        now = str(time.time())
        assert _verify_webhook_timestamp(now)

    def test_recent_timestamp_passes(self):
        """Timestamp from 1 minute ago should pass."""
        recent = str(time.time() - 60)
        assert _verify_webhook_timestamp(recent)

    def test_old_timestamp_rejects(self):
        """Timestamp from 10 minutes ago should be rejected."""
        old = str(time.time() - 600)
        assert not _verify_webhook_timestamp(old, provider="paddle")

    def test_future_timestamp_rejects(self):
        """Timestamp far in the future should be rejected."""
        future = str(time.time() + 600)
        assert not _verify_webhook_timestamp(future)

    def test_boundary_timestamp_passes(self):
        """Timestamp exactly at the freshness boundary should pass."""
        boundary = str(time.time() - _WEBHOOK_FRESHNESS_SECONDS + 1)
        assert _verify_webhook_timestamp(boundary)

    def test_boundary_timestamp_plus_one_rejects(self):
        """Timestamp just past the freshness boundary should fail."""
        over = str(time.time() - _WEBHOOK_FRESHNESS_SECONDS - 1)
        assert not _verify_webhook_timestamp(over)

    def test_empty_timestamp_rejects(self):
        """Empty timestamp should fail."""
        assert not _verify_webhook_timestamp("")

    def test_none_timestamp_rejects(self):
        """None timestamp should fail."""
        assert not _verify_webhook_timestamp(None)

    def test_non_numeric_timestamp_rejects(self):
        """Non-numeric timestamp string should fail."""
        assert not _verify_webhook_timestamp("not-a-number")
        assert not _verify_webhook_timestamp("2024-01-01")

    def test_float_timestamp_passes(self):
        """Float timestamp should work."""
        now = time.time()
        assert _verify_webhook_timestamp(str(now))
        assert _verify_webhook_timestamp(now)  # actual float

    def test_negative_timestamp_rejects(self):
        """Negative (epoch before 1970) should be rejected as stale."""
        assert not _verify_webhook_timestamp("-1000000")

    def test_zero_timestamp_rejects(self):
        """Timestamp 0 (1970-01-01) should be rejected as stale."""
        assert not _verify_webhook_timestamp("0")


# ═══════════════════════════════════════════════════════════════════
# Integration: Constant-time comparison
# ═══════════════════════════════════════════════════════════════════


class TestConstantTimeComparison:
    """Verify all functions use constant-time comparison (BC-011)."""

    def test_paddle_uses_compare_digest(self):
        """Paddle verification source uses hmac.compare_digest."""
        import inspect
        source = inspect.getsource(verify_paddle_signature)
        assert "compare_digest" in source

    def test_twilio_uses_compare_digest(self):
        """Twilio verification source uses hmac.compare_digest."""
        import inspect
        source = inspect.getsource(verify_twilio_signature)
        assert "compare_digest" in source

    def test_shopify_uses_compare_digest(self):
        """Shopify verification source uses hmac.compare_digest."""
        import inspect
        source = inspect.getsource(verify_shopify_hmac)
        assert "compare_digest" in source
