"""
Tests for HMAC Signature Verification (BC-011, BC-003)

Tests cover:
- Paddle: valid/invalid signature, wrong secret, empty payload, unicode
- Twilio: valid/invalid signature, wrong URL, tampered params
- Shopify: valid/invalid HMAC, missing header
- Brevo IP: valid IPs, invalid IP, empty IP, custom/default allowlist
- Constant-time: verify compare_digest is used in source
"""

import base64
import hashlib
import hmac
import inspect

from backend.app.security.hmac_verification import (
    DEFAULT_BREVO_IPS,
    verify_brevo_ip,
    verify_paddle_signature,
    verify_shopify_hmac,
    verify_twilio_signature,
)


# ── Paddle Tests ───────────────────────────────────────────────


class TestPaddleSignature:
    """Paddle HMAC-SHA256 signature verification."""

    def test_valid_signature(self):
        """Correct payload + secret + signature -> True."""
        secret = "paddle_webhook_secret_123"
        payload = b'{"event": "payment.completed"}'
        sig = hmac.new(
            secret.encode(), payload, hashlib.sha256,
        ).hexdigest()
        assert verify_paddle_signature(payload, sig, secret) is True

    def test_invalid_signature(self):
        """Wrong signature -> False."""
        assert verify_paddle_signature(
            b"{}", "bad_signature", "secret",
        ) is False

    def test_wrong_secret(self):
        """Right payload + right signature but wrong secret -> False."""
        payload = b"test"
        sig = hmac.new(
            b"correct", payload, hashlib.sha256,
        ).hexdigest()
        assert verify_paddle_signature(
            payload, sig, "wrong_secret",
        ) is False

    def test_empty_payload(self):
        """Empty payload -> False (fail-closed)."""
        assert verify_paddle_signature(
            b"", "any_sig", "secret",
        ) is False

    def test_empty_signature(self):
        """Empty signature -> False."""
        assert verify_paddle_signature(
            b"payload", "", "secret",
        ) is False

    def test_empty_secret(self):
        """Empty secret -> False."""
        assert verify_paddle_signature(
            b"payload", "any_sig", "",
        ) is False

    def test_unicode_payload(self):
        """Unicode payload (emoji) should work correctly."""
        secret = "test_secret"
        payload = '{"user": "\U0001f600"}'.encode("utf-8")
        sig = hmac.new(
            secret.encode(), payload, hashlib.sha256,
        ).hexdigest()
        assert verify_paddle_signature(
            payload, sig, secret,
        ) is True

    def test_signature_with_whitespace(self):
        """Signature with leading/trailing whitespace."""
        secret = "test"
        payload = b"data"
        sig = hmac.new(
            secret.encode(), payload, hashlib.sha256,
        ).hexdigest()
        assert verify_paddle_signature(
            payload, f"  {sig}  ", secret,
        ) is True


# ── Twilio Tests ───────────────────────────────────────────────


class TestTwilioSignature:
    """Twilio signature verification (RFC 5849)."""

    def _make_signature(self, url, params, auth_token):
        """Helper to generate valid Twilio signature."""
        sorted_params = sorted(params.items())
        data = url
        for key, value in sorted_params:
            data += key + str(value)
        return hmac.new(
            auth_token.encode(), data.encode(), hashlib.sha1,
        ).hexdigest()

    def test_valid_signature(self):
        """Correct URL + params + token -> True."""
        url = "https://example.com/webhook"
        params = {"CallSid": "CA123", "From": "+1234567890"}
        token = "twilio_auth_token"
        sig = self._make_signature(url, params, token)
        assert verify_twilio_signature(
            url, params, sig, token,
        ) is True

    def test_invalid_signature(self):
        """Wrong signature -> False."""
        assert verify_twilio_signature(
            "https://example.com/webhook",
            {"a": "b"}, "bad_sig", "token",
        ) is False

    def test_wrong_url(self):
        """Correct params but wrong URL -> False."""
        token = "twilio_auth_token"
        params = {"CallSid": "CA123"}
        sig = self._make_signature(
            "https://example.com/right", params, token,
        )
        assert verify_twilio_signature(
            "https://example.com/wrong", params, sig, token,
        ) is False

    def test_tampered_params(self):
        """Tampered params -> False."""
        token = "twilio_auth_token"
        params = {"CallSid": "CA123", "From": "+1234567890"}
        sig = self._make_signature(
            "https://example.com/webhook", params, token,
        )
        tampered = {"CallSid": "CA999", "From": "+1234567890"}
        assert verify_twilio_signature(
            "https://example.com/webhook", tampered, sig, token,
        ) is False

    def test_empty_url(self):
        """Empty URL -> False."""
        assert verify_twilio_signature(
            "", {"a": "b"}, "sig", "token",
        ) is False

    def test_empty_params(self):
        """Empty params -> False."""
        assert verify_twilio_signature(
            "https://example.com", {}, "sig", "token",
        ) is False

    def test_signature_with_whitespace(self):
        """Signature with whitespace should be stripped."""
        url = "https://example.com/webhook"
        params = {"a": "b"}
        token = "token"
        sig = self._make_signature(url, params, token)
        assert verify_twilio_signature(
            url, params, f"  {sig}  ", token,
        ) is True


# ── Shopify Tests ──────────────────────────────────────────────


class TestShopifyHMAC:
    """Shopify HMAC-SHA256 verification."""

    def test_valid_hmac(self):
        """Correct payload + secret + HMAC -> True."""
        secret = "shopify_secret"
        payload = b'{"id": 12345}'
        mac = hmac.new(
            secret.encode(), payload, hashlib.sha256,
        ).digest()
        sig = base64.b64encode(mac).decode("utf-8")
        assert verify_shopify_hmac(payload, sig, secret) is True

    def test_invalid_hmac(self):
        """Wrong HMAC -> False."""
        assert verify_shopify_hmac(
            b"{}", "invalid_hmac", "secret",
        ) is False

    def test_missing_header(self):
        """Empty HMAC header -> False."""
        assert verify_shopify_hmac(
            b"{}", "", "secret",
        ) is False

    def test_empty_secret(self):
        """Empty secret -> False."""
        assert verify_shopify_hmac(
            b"{}", "any_hmac", "",
        ) is False

    def test_wrong_secret(self):
        """Right HMAC but wrong secret -> False."""
        payload = b"data"
        mac = hmac.new(
            b"correct", payload, hashlib.sha256,
        ).digest()
        sig = base64.b64encode(mac).decode("utf-8")
        assert verify_shopify_hmac(
            payload, sig, "wrong_secret",
        ) is False

    def test_unicode_payload(self):
        """Unicode payload should work."""
        secret = "secret"
        payload = '{"name": "café"}'.encode("utf-8")
        mac = hmac.new(
            secret.encode(), payload, hashlib.sha256,
        ).digest()
        sig = base64.b64encode(mac).decode("utf-8")
        assert verify_shopify_hmac(payload, sig, secret) is True


# ── Brevo IP Tests ─────────────────────────────────────────────


class TestBrevoIP:
    """Brevo IP allowlist verification."""

    def test_valid_ip_in_range(self):
        """IP within Brevo range -> True."""
        assert verify_brevo_ip("185.107.232.1") is True

    def test_invalid_ip(self):
        """IP not in any Brevo range -> False."""
        assert verify_brevo_ip("8.8.8.8") is False

    def test_empty_ip(self):
        """Empty IP -> False."""
        assert verify_brevo_ip("") is False

    def test_none_ip(self):
        """None IP -> False."""
        assert verify_brevo_ip(None) is False

    def test_custom_allowlist(self):
        """Custom allowlist overrides default."""
        custom = ["10.0.0.0/8"]
        assert verify_brevo_ip("10.1.2.3", custom) is True
        assert verify_brevo_ip("185.107.232.1", custom) is False

    def test_default_brevo_ips_is_list(self):
        """Default Brevo IPs is a non-empty list."""
        assert isinstance(DEFAULT_BREVO_IPS, list)
        assert len(DEFAULT_BREVO_IPS) >= 4

    def test_all_default_ranges_covered(self):
        """All 4 documented Brevo ranges are in default."""
        assert "185.107.232.0/24" in DEFAULT_BREVO_IPS
        assert "102.134.48.0/24" in DEFAULT_BREVO_IPS
        assert "1.179.106.0/24" in DEFAULT_BREVO_IPS
        assert "185.107.236.0/24" in DEFAULT_BREVO_IPS

    def test_empty_allowlist_blocks_all(self):
        """Empty custom allowlist -> all IPs blocked."""
        assert verify_brevo_ip("1.2.3.4", []) is False

    def test_invalid_ip_format(self):
        """Invalid IP format -> False (fail-closed)."""
        assert verify_brevo_ip("not-an-ip") is False


# ── Constant-Time Comparison Tests ────────────────────────────


class TestConstantTimeComparison:
    """Verify hmac.compare_digest is used everywhere (BC-011)."""

    def test_paddle_uses_compare_digest(self):
        """Paddle verification source contains compare_digest."""
        source = inspect.getsource(verify_paddle_signature)
        assert "compare_digest" in source

    def test_twilio_uses_compare_digest(self):
        """Twilio verification source contains compare_digest."""
        source = inspect.getsource(verify_twilio_signature)
        assert "compare_digest" in source

    def test_shopify_uses_compare_digest(self):
        """Shopify verification source contains compare_digest."""
        source = inspect.getsource(verify_shopify_hmac)
        assert "compare_digest" in source

    def test_no_equality_operator_in_paddle(self):
        """Paddle source should NOT use == for sig comparison."""
        source = inspect.getsource(verify_paddle_signature)
        assert "== " not in source or "expected" not in source

    def test_fail_closed_all_functions(self):
        """All functions return False on empty/None inputs."""
        assert verify_paddle_signature(
            None, None, None,
        ) is False
        assert verify_twilio_signature(
            None, None, None, None,
        ) is False
        assert verify_shopify_hmac(None, None, None) is False
        assert verify_brevo_ip(None) is False
