"""
Tests for Paddle client fixes (Day 9):
- Webhook signature verification (ts={timestamp};h1={hash} format)
- Async rate limiting (asyncio.sleep instead of time.sleep)
- _parse_occurred_at bug fix
"""

import hashlib
import hmac
import time
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.clients.paddle_client import PaddleClient


# ════════════════════════════════════════════════════════════════
# FIXTURES
# ════════════════════════════════════════════════════════════════


@pytest.fixture
def paddle_client():
    """Create a PaddleClient with test credentials."""
    return PaddleClient(
        api_key="test_api_key",
        sandbox=True,
        webhook_secret="test_webhook_secret_key",
    )


def _make_paddle_signature(payload: bytes, secret: str, timestamp: int) -> str:
    """Generate a valid Paddle Billing API webhook signature."""
    signed_payload = f"{timestamp}:".encode() + payload
    h1 = hmac.new(
        secret.encode(),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()
    return f"ts={timestamp};h1={h1}"


# ════════════════════════════════════════════════════════════════
# WEBHOOK SIGNATURE TESTS
# ════════════════════════════════════════════════════════════════


class TestWebhookSignatureVerification:
    """Tests for Paddle webhook signature verification."""

    def test_valid_signature_ts_h1_format(self, paddle_client):
        """Valid ts={timestamp};h1={hash} signature should return True."""
        payload = b'{"event_type": "subscription.created", "data": {}}'
        ts = int(time.time())
        signature = _make_paddle_signature(payload, "test_webhook_secret_key", ts)

        assert paddle_client.verify_webhook_signature(payload, signature) is True

    def test_invalid_signature_wrong_hash(self, paddle_client):
        """Wrong hash should return False."""
        payload = b'{"event_type": "subscription.created"}'
        ts = int(time.time())
        signature = f"ts={ts};h1=wrong_hash_value"

        assert paddle_client.verify_webhook_signature(payload, signature) is False

    def test_invalid_signature_wrong_secret(self, paddle_client):
        """Signature created with wrong secret should return False."""
        payload = b'{"event_type": "subscription.created"}'
        ts = int(time.time())
        # Use wrong secret
        signed_payload = f"{ts}:".encode() + payload
        h1 = hmac.new(
            "wrong_secret".encode(),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()
        signature = f"ts={ts};h1={h1}"

        assert paddle_client.verify_webhook_signature(payload, signature) is False

    def test_replay_attack_expired_signature(self, paddle_client):
        """Signatures older than 5 minutes should be rejected."""
        payload = b'{"event_type": "subscription.created"}'
        # Timestamp from 10 minutes ago
        ts = int(time.time()) - 600
        signature = _make_paddle_signature(payload, "test_webhook_secret_key", ts)

        assert paddle_client.verify_webhook_signature(payload, signature) is False

    def test_signature_within_time_window(self, paddle_client):
        """Signatures within 5 minutes should be accepted."""
        payload = b'{"event_type": "subscription.created"}'
        # Timestamp from 4 minutes ago (within 5 min window)
        ts = int(time.time()) - 240
        signature = _make_paddle_signature(payload, "test_webhook_secret_key", ts)

        assert paddle_client.verify_webhook_signature(payload, signature) is True

    def test_malformed_signature_no_ts(self, paddle_client):
        """Missing ts field should return False."""
        payload = b'{"event_type": "subscription.created"}'
        signature = "h1=somehash"

        assert paddle_client.verify_webhook_signature(payload, signature) is False

    def test_malformed_signature_no_h1(self, paddle_client):
        """Missing h1 field should return False."""
        payload = b'{"event_type": "subscription.created"}'
        ts = int(time.time())
        signature = f"ts={ts}"

        assert paddle_client.verify_webhook_signature(payload, signature) is False

    def test_empty_signature(self, paddle_client):
        """Empty signature should return False."""
        payload = b'{"event_type": "subscription.created"}'

        assert paddle_client.verify_webhook_signature(payload, "") is False

    def test_no_webhook_secret(self):
        """Missing webhook secret should return False."""
        client = PaddleClient(api_key="test_key", webhook_secret=None)
        payload = b'{"event_type": "subscription.created"}'
        ts = int(time.time())
        signature = _make_paddle_signature(payload, "secret", ts)

        assert client.verify_webhook_signature(payload, signature) is False

    def test_empty_webhook_secret(self):
        """Empty webhook secret should return False."""
        client = PaddleClient(api_key="test_key", webhook_secret="")
        payload = b'{"event_type": "subscription.created"}'

        assert client.verify_webhook_signature(payload, "ts=123;h1=abc") is False

    def test_corrupted_payload(self, paddle_client):
        """Modified payload should fail verification."""
        original_payload = b'{"event_type": "subscription.created"}'
        ts = int(time.time())
        signature = _make_paddle_signature(
            original_payload, "test_webhook_secret_key", ts
        )
        # Tamper with payload
        tampered_payload = b'{"event_type": "subscription.updated"}'

        assert paddle_client.verify_webhook_signature(tampered_payload, signature) is False


# ════════════════════════════════════════════════════════════════
# ASYNC RATE LIMITING TESTS
# ════════════════════════════════════════════════════════════════


class TestAsyncRateLimiting:
    """Tests for async rate limit enforcement."""

    def test_rate_limit_wait_attribute_exists(self, paddle_client):
        """PaddleClient should have _rate_limit_wait attribute."""
        assert hasattr(paddle_client, "_rate_limit_wait")
        assert paddle_client._rate_limit_wait == 0

    def test_rate_limit_under_threshold(self, paddle_client):
        """Should not set wait time when under threshold."""
        # Add only a few requests (well under 500)
        for _ in range(10):
            paddle_client._request_times.append(time.time())

        paddle_client._check_rate_limit()
        assert paddle_client._rate_limit_wait == 0

    def test_rate_limit_over_threshold(self, paddle_client):
        """Should set wait time when over threshold."""
        now = time.time()
        # Fill up to threshold with recent timestamps
        for i in range(500):
            paddle_client._request_times.append(now - i * 0.01)

        paddle_client._check_rate_limit()
        assert paddle_client._rate_limit_wait > 0


# ════════════════════════════════════════════════════════════════
# PARSE OCCURRED_AT TESTS
# ════════════════════════════════════════════════════════════════


class TestParseOccurredAt:
    """Tests for _parse_occurred_at fix."""

    def test_parse_valid_iso_string(self):
        """Should parse valid ISO timestamp string."""
        from app.webhooks.paddle_handler import _parse_occurred_at

        event = {"occurred_at": "2025-07-14T10:30:00Z"}
        result = _parse_occurred_at(event)
        assert result.year == 2025
        assert result.month == 7
        assert result.day == 14

    def test_parse_iso_with_timezone(self):
        """Should parse ISO timestamp with timezone offset."""
        from app.webhooks.paddle_handler import _parse_occurred_at

        event = {"occurred_at": "2025-07-14T10:30:00+05:30"}
        result = _parse_occurred_at(event)
        assert result.year == 2025
        assert result.month == 7

    def test_parse_missing_occurred_at(self):
        """Should return current time when occurred_at is missing."""
        from app.webhooks.paddle_handler import _parse_occurred_at
        import datetime

        event = {}
        before = datetime.datetime.now(datetime.timezone.utc)
        result = _parse_occurred_at(event)
        after = datetime.datetime.now(datetime.timezone.utc)
        assert before <= result <= after

    def test_parse_none_occurred_at(self):
        """Should return current time when occurred_at is None."""
        from app.webhooks.paddle_handler import _parse_occurred_at
        import datetime

        event = {"occurred_at": None}
        before = datetime.datetime.now(datetime.timezone.utc)
        result = _parse_occurred_at(event)
        after = datetime.datetime.now(datetime.timezone.utc)
        assert before <= result <= after

    def test_parse_invalid_string(self):
        """Should return current time for invalid string."""
        from app.webhooks.paddle_handler import _parse_occurred_at
        import datetime

        event = {"occurred_at": "not-a-date"}
        before = datetime.datetime.now(datetime.timezone.utc)
        result = _parse_occurred_at(event)
        after = datetime.datetime.now(datetime.timezone.utc)
        assert before <= result <= after

    def test_parse_datetime_object(self):
        """Should pass through datetime objects unchanged."""
        from app.webhooks.paddle_handler import _parse_occurred_at
        import datetime

        dt = datetime.datetime(2025, 7, 14, 10, 30, 0, tzinfo=datetime.timezone.utc)
        event = {"occurred_at": dt}
        result = _parse_occurred_at(event)
        assert result == dt
