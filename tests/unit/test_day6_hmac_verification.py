"""
Comprehensive HMAC Verification Tests (Day 6 - BC-011, BC-003, BC-008)

Tests cover:
- Paddle HMAC-SHA256: valid/invalid signatures, empty inputs, whitespace trim, no exceptions
- Twilio RFC 5849: valid/invalid signatures, sorted params, empty inputs, no exceptions
- Shopify HMAC-SHA256 base64: valid/invalid signatures, empty inputs, no exceptions
- Brevo IP allowlist: default ranges, custom ranges, env var, invalid IPs, no exceptions
- Webhook timestamp freshness: fresh, stale, future, invalid, boundary, no exceptions
- BC-008: All verify functions never raise exceptions on any input
- BC-011: All verify functions use hmac.compare_digest (constant-time)
"""

import base64
import hashlib
import hmac as hmac_mod
import inspect
import os
import time
from unittest import mock

import pytest

from backend.app.security.hmac_verification import (
    DEFAULT_BREVO_IPS,
    _get_brevo_ips,
    _verify_webhook_timestamp,
    verify_brevo_ip,
    verify_paddle_signature,
    verify_shopify_hmac,
    verify_twilio_signature,
)


# ── Paddle Signature Tests ────────────────────────────────────


class TestPaddleSignature:
    """Paddle HMAC-SHA256 hex signature verification."""

    def test_valid_signature_returns_true(self):
        """Correct payload + secret + signature → True."""
        secret = "paddle_webhook_secret_123"
        payload = b'{"event": "payment.completed", "data": {}}'
        expected_sig = hmac_mod.new(
            secret.encode("utf-8"), payload, hashlib.sha256,
        ).hexdigest()
        assert verify_paddle_signature(payload, expected_sig, secret) is True

    def test_invalid_signature_returns_false(self):
        """Wrong signature → False."""
        assert verify_paddle_signature(
            b'{"event": "test"}', "deadbeef00112233445566778899aabbccddeeff",
            "secret",
        ) is False

    def test_empty_payload_returns_false(self):
        """Empty payload bytes → False (fail-closed BC-008)."""
        assert verify_paddle_signature(b"", "somesig", "secret") is False

    def test_empty_secret_returns_false(self):
        """Empty secret → False."""
        assert verify_paddle_signature(
            b"payload", "somesig", "",
        ) is False

    def test_empty_signature_returns_false(self):
        """Empty signature header → False."""
        assert verify_paddle_signature(b"payload", "", "secret") is False

    def test_whitespace_in_signature_is_trimmed(self):
        """Whitespace around signature header is stripped before compare."""
        secret = "test_secret"
        payload = b"data"
        sig = hmac_mod.new(
            secret.encode("utf-8"), payload, hashlib.sha256,
        ).hexdigest()
        assert verify_paddle_signature(
            payload, f"  \t{sig}\n  ", secret,
        ) is True

    def test_wrong_secret_returns_false(self):
        """Correct signature but wrong secret → False."""
        payload = b"test_payload"
        sig = hmac_mod.new(
            b"correct_secret", payload, hashlib.sha256,
        ).hexdigest()
        assert verify_paddle_signature(
            payload, sig, "wrong_secret",
        ) is False

    def test_unicode_payload(self):
        """Unicode payload (emoji) works correctly."""
        secret = "test_secret"
        payload = '{"user": "😀"}'.encode("utf-8")
        sig = hmac_mod.new(
            secret.encode("utf-8"), payload, hashlib.sha256,
        ).hexdigest()
        assert verify_paddle_signature(payload, sig, secret) is True


# ── Twilio Signature Tests ────────────────────────────────────


class TestTwilioSignature:
    """Twilio RFC 5849 HMAC-SHA1 signature verification."""

    @staticmethod
    def _make_twilio_sig(url: str, params: dict, auth_token: str) -> str:
        """Generate a valid Twilio signature for testing."""
        sorted_params = sorted(params.items())
        data = url
        for key, value in sorted_params:
            data += key + str(value)
        return hmac_mod.new(
            auth_token.encode("utf-8"), data.encode("utf-8"), hashlib.sha1,
        ).hexdigest()

    def test_valid_signature_returns_true(self):
        """Correct URL + sorted params + token → True."""
        url = "https://api.example.com/webhook/twilio"
        params = {"CallSid": "CA123456", "From": "+1234567890", "To": "+0987654321"}
        token = "twilio_auth_token_xyz"
        sig = self._make_twilio_sig(url, params, token)
        assert verify_twilio_signature(url, params, sig, token) is True

    def test_invalid_signature_returns_false(self):
        """Wrong signature → False."""
        assert verify_twilio_signature(
            "https://example.com/webhook",
            {"a": "b"}, "bad_sig_value", "token",
        ) is False

    def test_empty_params_returns_false(self):
        """Empty params dict → False."""
        assert verify_twilio_signature(
            "https://example.com", {}, "sig", "token",
        ) is False

    def test_params_are_sorted_before_signing(self):
        """Verify that params are sorted lexicographically before signing."""
        url = "https://example.com/hook"
        # Use same params but in different insertion order — signature
        # should be identical because sorting happens inside
        params_unordered = {"z_key": "val2", "a_key": "val1"}
        params_sorted = {"a_key": "val1", "z_key": "val2"}
        token = "my_token"
        sig = self._make_twilio_sig(url, params_unordered, token)
        assert verify_twilio_signature(url, params_sorted, sig, token) is True

    def test_tampered_params_returns_false(self):
        """Changing a param value invalidates the signature."""
        url = "https://example.com/hook"
        params = {"CallSid": "CA123", "From": "+1111111111"}
        token = "tok"
        sig = self._make_twilio_sig(url, params, token)
        tampered = {"CallSid": "CA999", "From": "+1111111111"}
        assert verify_twilio_signature(url, tampered, sig, token) is False

    def test_wrong_url_returns_false(self):
        """Correct params but wrong URL → False."""
        token = "tok"
        params = {"a": "b"}
        sig = self._make_twilio_sig("https://example.com/right", params, token)
        assert verify_twilio_signature(
            "https://example.com/wrong", params, sig, token,
        ) is False

    def test_empty_url_returns_false(self):
        """Empty URL → False."""
        assert verify_twilio_signature(
            "", {"a": "b"}, "sig", "token",
        ) is False

    def test_empty_auth_token_returns_false(self):
        """Empty auth_token → False."""
        assert verify_twilio_signature(
            "https://example.com", {"a": "b"}, "sig", "",
        ) is False

    def test_whitespace_in_signature_is_trimmed(self):
        """Whitespace around Twilio signature is stripped."""
        url = "https://example.com/hook"
        params = {"k": "v"}
        token = "tok"
        sig = self._make_twilio_sig(url, params, token)
        assert verify_twilio_signature(
            url, params, f"  {sig}  ", token,
        ) is True


# ── Shopify HMAC Tests ────────────────────────────────────────


class TestShopifyHMAC:
    """Shopify HMAC-SHA256 base64 signature verification."""

    def test_valid_base64_signature_returns_true(self):
        """Correct payload + secret + base64 HMAC → True."""
        secret = "shopify_app_secret"
        payload = b'{"id": 9876543210, "topic": "orders/create"}'
        mac = hmac_mod.new(
            secret.encode("utf-8"), payload, hashlib.sha256,
        ).digest()
        sig = base64.b64encode(mac).decode("utf-8")
        assert verify_shopify_hmac(payload, sig, secret) is True

    def test_invalid_signature_returns_false(self):
        """Wrong base64 HMAC → False."""
        assert verify_shopify_hmac(
            b'{"id": 1}', "aW52YWxpZA==", "secret",
        ) is False

    def test_empty_payload_returns_false(self):
        """Empty payload bytes → False (fail-closed)."""
        assert verify_shopify_hmac(b"", "aW52YWxpZA==", "secret") is False

    def test_empty_hmac_header_returns_false(self):
        """Empty HMAC header → False."""
        assert verify_shopify_hmac(b"payload", "", "secret") is False

    def test_empty_secret_returns_false(self):
        """Empty secret → False."""
        assert verify_shopify_hmac(b"payload", "aW52YWxpZA==", "") is False

    def test_wrong_secret_returns_false(self):
        """Right payload + right HMAC but wrong secret → False."""
        payload = b"shopify_order_data"
        mac = hmac_mod.new(
            b"correct_secret", payload, hashlib.sha256,
        ).digest()
        sig = base64.b64encode(mac).decode("utf-8")
        assert verify_shopify_hmac(payload, sig, "wrong_secret") is False

    def test_unicode_payload(self):
        """Unicode payload (accented chars) works."""
        secret = "s"
        payload = '{"name": "café résumé"}'.encode("utf-8")
        mac = hmac_mod.new(
            secret.encode("utf-8"), payload, hashlib.sha256,
        ).digest()
        sig = base64.b64encode(mac).decode("utf-8")
        assert verify_shopify_hmac(payload, sig, secret) is True


# ── Brevo IP Tests ────────────────────────────────────────────


class TestBrevoIP:
    """Brevo IP allowlist verification."""

    def test_ip_in_default_range_returns_true(self):
        """IP 185.107.232.1 is within default Brevo range 185.107.232.0/24."""
        assert verify_brevo_ip("185.107.232.1") is True

    def test_ip_not_in_range_returns_false(self):
        """Google DNS IP 8.8.8.8 is NOT in Brevo range → False."""
        assert verify_brevo_ip("8.8.8.8") is False

    def test_empty_ip_returns_false(self):
        """Empty IP string → False."""
        assert verify_brevo_ip("") is False

    def test_none_ip_returns_false(self):
        """None IP → False."""
        assert verify_brevo_ip(None) is False

    def test_custom_allowed_ips_overrides_default(self):
        """When custom allowed_ips list is passed, default is NOT used."""
        custom = ["10.0.0.0/8", "172.16.0.0/12"]
        assert verify_brevo_ip("10.50.1.2", custom) is True
        assert verify_brevo_ip("172.16.5.5", custom) is True
        assert verify_brevo_ip("185.107.232.1", custom) is False

    def test_custom_empty_allowlist_blocks_all(self):
        """Empty custom allowlist → all IPs blocked."""
        assert verify_brevo_ip("185.107.232.1", []) is False
        assert verify_brevo_ip("1.1.1.1", []) is False

    def test_env_var_brevo_ip_ranges_used(self):
        """When BREVO_IP_RANGES env var is set, it's used by _get_brevo_ips."""
        custom_cidr = "99.99.99.0/24"
        with mock.patch.dict(os.environ, {"BREVO_IP_RANGES": custom_cidr}):
            ips = _get_brevo_ips()
            assert custom_cidr in ips

    def test_env_var_brevo_ip_ranges_fallback_on_invalid(self):
        """Invalid BREVO_IP_RANGES env var falls back to defaults."""
        with mock.patch.dict(os.environ, {"BREVO_IP_RANGES": "not-a-cidr"}):
            ips = _get_brevo_ips()
            assert ips == DEFAULT_BREVO_IPS

    def test_env_var_brevo_ip_ranges_multiple(self):
        """Multiple CIDRs in BREVO_IP_RANGES env var are parsed."""
        cidrs = "10.0.0.0/8, 192.168.0.0/16"
        with mock.patch.dict(os.environ, {"BREVO_IP_RANGES": cidrs}):
            ips = _get_brevo_ips()
            assert "10.0.0.0/8" in ips
            assert "192.168.0.0/16" in ips

    def test_all_default_ranges_are_present(self):
        """DEFAULT_BREVO_IPS contains all 4 documented ranges."""
        assert "185.107.232.0/24" in DEFAULT_BREVO_IPS
        assert "102.134.48.0/24" in DEFAULT_BREVO_IPS
        assert "1.179.106.0/24" in DEFAULT_BREVO_IPS
        assert "185.107.236.0/24" in DEFAULT_BREVO_IPS

    def test_invalid_ip_format_returns_false(self):
        """Malformed IP string → False (fail-closed)."""
        assert verify_brevo_ip("not-an-ip-address") is False
        assert verify_brevo_ip("999.999.999.999") is False

    def test_ip_with_whitespace_is_trimmed(self):
        """IP with surrounding whitespace is trimmed before check."""
        assert verify_brevo_ip("  185.107.232.1  ") is True


# ── Webhook Timestamp Tests ───────────────────────────────────


class TestWebhookTimestamp:
    """Webhook timestamp freshness verification."""

    def test_fresh_timestamp_returns_true(self):
        """Timestamp from right now → True."""
        now = str(time.time())
        assert _verify_webhook_timestamp(now) is True

    def test_old_timestamp_returns_false(self):
        """Timestamp > 5 minutes ago → False."""
        old = str(time.time() - 600)  # 10 minutes ago
        assert _verify_webhook_timestamp(old) is False

    def test_future_timestamp_returns_false(self):
        """Timestamp > 5 minutes in the future → False."""
        future = str(time.time() + 600)  # 10 minutes from now
        assert _verify_webhook_timestamp(future) is False

    def test_invalid_string_returns_false(self):
        """Non-numeric string → False."""
        assert _verify_webhook_timestamp("not-a-timestamp") is False
        assert _verify_webhook_timestamp("abc123") is False

    def test_none_timestamp_returns_false(self):
        """None → False."""
        assert _verify_webhook_timestamp(None) is False

    def test_empty_string_returns_false(self):
        """Empty string → False."""
        assert _verify_webhook_timestamp("") is False

    def test_boundary_exactly_300_seconds_returns_true(self):
        """Exactly 300 seconds (5 min) → True (abs(age) > 300 is False).

        Use mock to avoid floating-point timing race.
        """
        now = 1000000.0
        ts = str(now - 300)
        with mock.patch("backend.app.security.hmac_verification.time.time", return_value=now):
            assert _verify_webhook_timestamp(ts) is True

    def test_boundary_301_seconds_returns_false(self):
        """301 seconds (> 5 min) → False.

        Use mock to avoid floating-point timing race.
        """
        now = 1000000.0
        ts = str(now - 301)
        with mock.patch("backend.app.security.hmac_verification.time.time", return_value=now):
            assert _verify_webhook_timestamp(ts) is False

    def test_provider_name_accepted(self):
        """Provider name is accepted without affecting result."""
        now = str(time.time())
        assert _verify_webhook_timestamp(now, provider="paddle") is True
        assert _verify_webhook_timestamp(
            str(time.time() - 600), provider="shopify",
        ) is False


# ── BC-008: No Exceptions ────────────────────────────────────


class TestNoExceptions:
    """BC-008: All verify functions must NEVER raise exceptions."""

    def test_paddle_none_payload_no_raise(self):
        """verify_paddle_signature(None, sig, secret) → bool, no raise."""
        assert isinstance(verify_paddle_signature(None, "sig", "s"), bool)

    def test_paddle_none_sig_no_raise(self):
        """verify_paddle_signature(b'x', None, 's') → bool, no raise."""
        assert isinstance(verify_paddle_signature(b"x", None, "s"), bool)

    def test_paddle_none_secret_no_raise(self):
        """verify_paddle_signature(b'x', 'sig', None) → bool, no raise."""
        assert isinstance(verify_paddle_signature(b"x", "sig", None), bool)

    def test_paddle_non_bytes_payload_no_raise(self):
        """verify_paddle_signature(12345, 'sig', 's') → bool, no raise."""
        assert isinstance(verify_paddle_signature(12345, "sig", "s"), bool)

    def test_paddle_non_str_signature_no_raise(self):
        """verify_paddle_signature(b'x', 999, 's') → bool, no raise."""
        assert isinstance(verify_paddle_signature(b"x", 999, "s"), bool)

    def test_twilio_none_url_no_raise(self):
        """verify_twilio_signature(None, params, sig, token) → bool."""
        assert isinstance(
            verify_twilio_signature(None, {"a": "b"}, "s", "t"), bool,
        )

    def test_twilio_none_params_no_raise(self):
        """verify_twilio_signature(url, None, sig, token) → bool."""
        assert isinstance(
            verify_twilio_signature("u", None, "s", "t"), bool,
        )

    def test_twilio_none_sig_no_raise(self):
        """verify_twilio_signature(url, params, None, token) → bool."""
        assert isinstance(
            verify_twilio_signature("u", {"a": "b"}, None, "t"), bool,
        )

    def test_twilio_none_token_no_raise(self):
        """verify_twilio_signature(url, params, sig, None) → bool."""
        assert isinstance(
            verify_twilio_signature("u", {"a": "b"}, "s", None), bool,
        )

    def test_twilio_non_str_url_no_raise(self):
        """verify_twilio_signature(123, params, sig, token) → bool."""
        assert isinstance(
            verify_twilio_signature(123, {"a": "b"}, "s", "t"), bool,
        )

    def test_shopify_none_payload_no_raise(self):
        """verify_shopify_hmac(None, hmac, secret) → bool."""
        assert isinstance(verify_shopify_hmac(None, "h", "s"), bool)

    def test_shopify_none_hmac_no_raise(self):
        """verify_shopify_hmac(b'x', None, 's') → bool."""
        assert isinstance(verify_shopify_hmac(b"x", None, "s"), bool)

    def test_shopify_none_secret_no_raise(self):
        """verify_shopify_hmac(b'x', 'h', None) → bool."""
        assert isinstance(verify_shopify_hmac(b"x", "h", None), bool)

    def test_shopify_non_bytes_payload_no_raise(self):
        """verify_shopify_hmac('str', 'h', 's') → bool."""
        assert isinstance(
            verify_shopify_hmac("not-bytes", "h", "s"), bool,
        )

    def test_brevo_non_str_ip_no_raise(self):
        """verify_brevo_ip(12345) → bool."""
        assert isinstance(verify_brevo_ip(12345), bool)

    def test_brevo_invalid_cidr_no_raise(self):
        """verify_brevo_ip('1.2.3.4', ['bad-cidr']) → bool."""
        assert isinstance(
            verify_brevo_ip("1.2.3.4", ["bad-cidr"]), bool,
        )

    def test_timestamp_none_no_raise(self):
        """_verify_webhook_timestamp(None) → bool."""
        assert isinstance(_verify_webhook_timestamp(None), bool)

    def test_timestamp_non_numeric_no_raise(self):
        """_verify_webhook_timestamp('not-a-number') → bool."""
        assert isinstance(
            _verify_webhook_timestamp("not-a-number"), bool,
        )

    def test_timestamp_bytes_no_raise(self):
        """_verify_webhook_timestamp(b'bytes') → bool."""
        assert isinstance(_verify_webhook_timestamp(b"bytes"), bool)


# ── BC-011: Constant-Time Comparison ─────────────────────────


class TestConstantTimeComparison:
    """BC-011: All verify functions use hmac.compare_digest."""

    def test_paddle_uses_compare_digest(self):
        """Paddle source must contain hmac.compare_digest."""
        source = inspect.getsource(verify_paddle_signature)
        assert "compare_digest" in source

    def test_twilio_uses_compare_digest(self):
        """Twilio source must contain hmac.compare_digest."""
        source = inspect.getsource(verify_twilio_signature)
        assert "compare_digest" in source

    def test_shopify_uses_compare_digest(self):
        """Shopify source must contain hmac.compare_digest."""
        source = inspect.getsource(verify_shopify_hmac)
        assert "compare_digest" in source

    def test_brevo_no_timing_attack_surface(self):
        """Brevo IP uses ipaddress module (no string comparison timing issue)."""
        source = inspect.getsource(verify_brevo_ip)
        # Should use ipaddress.ip_address and ipaddress.ip_network
        assert "ip_address" in source
        assert "ip_network" in source

    def test_no_equality_in_signature_compare(self):
        """Paddle and Shopify should NOT use == for signature comparison."""
        for func in [verify_paddle_signature, verify_twilio_signature, verify_shopify_hmac]:
            source = inspect.getsource(func)
            # The only == should be part of .startswith or other non-sig logic
            lines = source.split("\n")
            for line in lines:
                stripped = line.strip()
                # Skip comments and lines that aren't sig comparisons
                if stripped.startswith("#") or "return" not in stripped:
                    continue
                # Should not have `expected == sig` pattern
                assert "expected ==" not in stripped
                assert "== expected" not in stripped
