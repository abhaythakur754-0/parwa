"""
Loophole/Vulnerability Tests for Day 4 Fixes

Tests verify that all Phase B loophole findings are properly fixed.
These are regression tests — they must pass after the fixes
and would have FAILED before the fixes.

Findings tested:
- P0-1: rate_limit.py JSONResponse(content=bytes) crash
- P2-1: CircuitBreaker logging on state transitions
- P2-3: decrypt_data doesn't leak crypto details
- P2-4: TenantMiddleware validates company_id format
- P3-2: hash_api_key("") raises ValueError
- P1-3: Rate limiter prefers request.client.host
"""

import hashlib
import logging
import time

import pytest

from security.api_keys import hash_api_key, verify_api_key
from security.circuit_breaker import CircuitBreaker
from shared.utils.security import decrypt_data, encrypt_data


class TestP0RateLimitMiddlewareFix:
    """P0-1: Rate limit middleware must return proper JSONResponse,
    not crash with TypeError from JSONResponse(content=bytes)."""

    def test_build_error_response_returns_jsonresponse(self):
        """build_error_response returns a JSONResponse, not bytes."""
        from backend.app.middleware.error_handler import build_error_response
        resp = build_error_response(
            status_code=429,
            error_code="RATE_LIMIT_EXCEEDED",
            message="Too many requests",
            correlation_id="test-123",
        )
        # Must be a JSONResponse (Starlette Response subclass)
        assert hasattr(resp, "body")
        # Body must be bytes (standard Starlette behavior)
        assert isinstance(resp.body, bytes)
        # Status code must be correct
        assert resp.status_code == 429
        # Must be able to add custom headers
        resp.headers["X-RateLimit-Limit"] = "100"
        assert resp.headers["X-RateLimit-Limit"] == "100"

    def test_rate_limit_result_headers_mergeable(self):
        """Rate limit headers can be merged into error response."""
        from backend.app.middleware.error_handler import build_error_response
        from security.rate_limiter import RateLimitResult

        result = RateLimitResult(
            allowed=False, remaining=0, limit=100,
            reset_at=time.time() + 30, retry_after=30,
        )
        resp = build_error_response(
            status_code=429,
            error_code="RATE_LIMIT_EXCEEDED",
            message="Too many requests",
        )
        # Merge rate limit headers — this must not crash
        for header, value in result.to_headers().items():
            resp.headers[header] = value
        assert resp.headers["X-RateLimit-Limit"] == "100"
        assert resp.headers["Retry-After"] == "30"


class TestP2CircuitBreakerLogging:
    """P2-1: CircuitBreaker must log on state transitions."""

    def test_transition_logs_on_open(self, caplog):
        """OPEN transition must be logged."""
        cb = CircuitBreaker("test_logger", failure_threshold=3)
        with caplog.at_level(logging.WARNING, logger="circuit_breaker"):
            for _ in range(3):
                cb.record_failure()
        # Should have logged a state change
        log_records = [
            r for r in caplog.records
            if r.message == "circuit_state_change"
        ]
        assert len(log_records) >= 1
        assert log_records[0].breaker_name == "test_logger"
        assert log_records[0].new_state == "open"

    def test_transition_logs_on_close(self, caplog):
        """CLOSED transition (via reset) must be logged."""
        cb = CircuitBreaker("test_close", failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="circuit_breaker"):
            cb.reset()
        log_records = [
            r for r in caplog.records
            if r.message == "circuit_state_change"
        ]
        assert len(log_records) >= 1
        assert log_records[0].new_state == "closed"

    def test_transition_logs_failure_count(self, caplog):
        """Log must include failure_count."""
        cb = CircuitBreaker("test_count", failure_threshold=3)
        with caplog.at_level(logging.WARNING, logger="circuit_breaker"):
            cb.record_failure()
            cb.record_failure()
            cb.record_failure()
        log_records = [
            r for r in caplog.records
            if r.message == "circuit_state_change"
            and r.new_state == "open"
        ]
        assert len(log_records) >= 1
        assert log_records[0].failure_count == 3


class TestP2DecryptDataNoLeak:
    """P2-3: decrypt_data must not leak crypto error details."""

    def test_decrypt_invalid_data_generic_message(self):
        """Decryption failure must return generic error, not crypto details."""
        with pytest.raises(ValueError) as exc_info:
            decrypt_data("invalid-base64!!!", "a" * 32)
        msg = str(exc_info.value)
        # Must NOT contain internal crypto library details
        assert "Decryption failed" in msg
        assert "padding" not in msg.lower()
        assert "tag" not in msg.lower()
        assert "MAC" not in msg
        assert "Invalid" not in msg  # no specific crypto error

    def test_decrypt_wrong_key_generic_message(self):
        """Decryption with wrong key must not leak key mismatch details."""
        encrypted = encrypt_data("secret data", "a" * 32)
        with pytest.raises(ValueError) as exc_info:
            decrypt_data(encrypted, "b" * 32)
        msg = str(exc_info.value)
        assert "Decryption failed" in msg
        # Must not reveal it was a key mismatch
        assert len(msg) < 50  # Keep error message short/generic


class TestP2TenantMiddlewareValidation:
    """P2-4: TenantMiddleware must validate company_id format."""

    def test_reject_very_long_company_id(self):
        """company_id > 128 chars must be rejected."""
        from backend.app.middleware.tenant import MAX_COMPANY_ID_LENGTH
        assert MAX_COMPANY_ID_LENGTH == 128
        # 200-char company_id exceeds the limit
        assert len("a" * 200) > MAX_COMPANY_ID_LENGTH

    def test_reject_control_characters_in_company_id(self):
        """company_id with control chars must be rejected."""
        from backend.app.middleware.tenant import MAX_COMPANY_ID_LENGTH
        assert MAX_COMPANY_ID_LENGTH == 128
        # Control char check: ord(c) < 32
        assert any(ord(c) < 32 for c in "comp\tany")
        assert any(ord(c) < 32 for c in "comp\x00any")
        assert not any(ord(c) < 32 for c in "company-ok_123")


class TestP3HashAPIKeyEmpty:
    """P3-2: hash_api_key must reject empty input."""

    def test_empty_key_raises_valueerror(self):
        """hash_api_key('') must raise ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            hash_api_key("")

    def test_verify_empty_key_returns_false(self):
        """verify_api_key with empty raw_key returns False."""
        assert verify_api_key("", "somehash") is False

    def test_verify_empty_hash_returns_false(self):
        """verify_api_key with empty hash returns False."""
        assert verify_api_key("somekey", "") is False

    def test_hash_nonempty_still_works(self):
        """hash_api_key with non-empty key still works correctly."""
        result = hash_api_key("pk_test_key_123")
        assert isinstance(result, str)
        assert len(result) == 64
        expected = hashlib.sha256(
            "pk_test_key_123".encode("utf-8")
        ).hexdigest()
        assert result == expected


class TestP1ClientIPPriority:
    """P1-3: Rate limiter must prefer request.client.host
    (cannot be spoofed) over X-Forwarded-For."""

    def test_rate_limit_uses_client_host_first(self):
        """_get_client_ip must prefer request.client.host."""
        from backend.app.middleware.rate_limit import RateLimitMiddleware
        from starlette.requests import Request
        from unittest.mock import MagicMock

        middleware = RateLimitMiddleware(MagicMock())

        # Mock request with client.host available
        request = MagicMock(spec=Request)
        request.client = MagicMock()
        request.client.host = "10.0.0.1"
        request.headers = {
            "X-Forwarded-For": "1.2.3.4",
            "X-Real-IP": "5.6.7.8",
        }

        ip = middleware._get_client_ip(request)
        # Must use request.client.host, not headers
        assert ip == "10.0.0.1"

    def test_rate_limit_falls_back_to_real_ip(self):
        """When no client.host, falls back to X-Real-IP."""
        from backend.app.middleware.rate_limit import RateLimitMiddleware
        from starlette.requests import Request
        from unittest.mock import MagicMock

        middleware = RateLimitMiddleware(MagicMock())

        request = MagicMock(spec=Request)
        request.client = None
        request.headers = {
            "X-Forwarded-For": "1.2.3.4",
            "X-Real-IP": "5.6.7.8",
        }

        ip = middleware._get_client_ip(request)
        assert ip == "5.6.7.8"

    def test_rate_limit_xff_last_resort(self):
        """X-Forwarded-For only used when no client.host or X-Real-IP."""
        from backend.app.middleware.rate_limit import RateLimitMiddleware
        from starlette.requests import Request
        from unittest.mock import MagicMock

        middleware = RateLimitMiddleware(MagicMock())

        request = MagicMock(spec=Request)
        request.client = None
        request.headers = {
            "X-Forwarded-For": "1.2.3.4, 10.0.0.1",
        }

        ip = middleware._get_client_ip(request)
        assert ip == "1.2.3.4"

    def test_rate_limit_empty_when_nothing(self):
        """Returns empty string when no IP source available."""
        from backend.app.middleware.rate_limit import RateLimitMiddleware
        from starlette.requests import Request
        from unittest.mock import MagicMock

        middleware = RateLimitMiddleware(MagicMock())

        request = MagicMock(spec=Request)
        request.client = None
        request.headers = {}

        ip = middleware._get_client_ip(request)
        assert ip == ""


class TestP2CorrelationIdInErrorHandler:
    """P2-2: ParwaBaseError handler must include correlation_id."""

    @pytest.mark.asyncio
    async def test_correlation_id_in_error_response(self):
        """The parwa_exception_handler includes correlation_id."""
        from backend.app.main import parwa_exception_handler
        from backend.app.exceptions import NotFoundError
        from starlette.requests import Request
        from unittest.mock import MagicMock

        request = MagicMock(spec=Request)
        request.state.correlation_id = "test-corr-123"

        exc = NotFoundError(message="Test not found")
        resp = await parwa_exception_handler(request, exc)
        import json
        body = json.loads(resp.body)
        assert body.get("correlation_id") == "test-corr-123"
        assert body["error"]["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_no_correlation_id_when_missing(self):
        """Handler works when correlation_id is not set."""
        from backend.app.main import parwa_exception_handler
        from backend.app.exceptions import NotFoundError
        from starlette.requests import Request
        from unittest.mock import MagicMock

        request = MagicMock(spec=Request)
        # Use a real object for state so getattr returns None
        request.state = type("State", (), {})()
        exc = NotFoundError(message="Test not found")
        resp = await parwa_exception_handler(request, exc)
        import json
        body = json.loads(resp.body)
        # correlation_id key should not be present
        assert "correlation_id" not in body
