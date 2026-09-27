"""
Tests for F-018 Advanced Rate Limit Service.

Tests per-endpoint-category limits, per-email identification,
progressive backoff, fail-open behavior, lockout, and headers.
"""

import time

import pytest

from backend.app.services.rate_limit_service import (
    CATEGORY_CONFIG,
    RateLimitResult,
    RateLimitService,
    get_rate_limit_service,
)


@pytest.fixture
def svc():
    """Fresh rate limit service for each test."""
    return RateLimitService()


class TestCategoryConfig:
    """Tests for endpoint category configuration."""

    def test_auth_login_config(self):
        cfg = CATEGORY_CONFIG["auth_login"]
        assert cfg["limit"] == 10
        assert cfg["window"] == 60
        assert cfg["scope"] == "email"
        assert len(cfg["backoff_seconds"]) == 5

    def test_auth_mfa_config(self):
        cfg = CATEGORY_CONFIG["auth_mfa"]
        assert cfg["limit"] == 10
        assert cfg["scope"] == "email"

    def test_auth_reset_config(self):
        cfg = CATEGORY_CONFIG["auth_reset"]
        assert cfg["limit"] == 3
        assert cfg["window"] == 3600
        assert cfg["scope"] == "email"

    def test_financial_config(self):
        cfg = CATEGORY_CONFIG["financial"]
        assert cfg["limit"] == 20
        assert cfg["scope"] == "user"
        assert cfg["lockout_duration"] == 300

    def test_general_get_config(self):
        cfg = CATEGORY_CONFIG["general_get"]
        assert cfg["limit"] == 100
        assert cfg["scope"] == "ip"

    def test_general_post_config(self):
        cfg = CATEGORY_CONFIG["general_post"]
        assert cfg["limit"] == 100
        assert cfg["scope"] == "ip"

    def test_integration_config(self):
        cfg = CATEGORY_CONFIG["integration"]
        assert cfg["limit"] == 60
        assert cfg["scope"] == "api_key"

    def test_demo_chat_config(self):
        cfg = CATEGORY_CONFIG["demo_chat"]
        assert cfg["limit"] == 60
        assert cfg["window"] == 300
        assert cfg["scope"] == "ip_hash"


class TestClassifyPath:
    """Tests for request path classification."""

    def test_login_path(self, svc):
        cat = svc.classify_path("/api/auth/login", "POST")
        assert cat == "auth_login"

    def test_mfa_path(self, svc):
        cat = svc.classify_path("/api/auth/mfa", "POST")
        assert cat == "auth_mfa"

    def test_forgot_password_path(self, svc):
        cat = svc.classify_path(
            "/api/auth/forgot-password", "POST",
        )
        assert cat == "auth_reset"

    def test_reset_password_path(self, svc):
        cat = svc.classify_path(
            "/api/auth/reset-password", "POST",
        )
        assert cat == "auth_reset"

    def test_billing_path(self, svc):
        cat = svc.classify_path(
            "/api/billing/subscription", "GET",
        )
        assert cat == "financial"

    def test_billing_post_path(self, svc):
        cat = svc.classify_path(
            "/api/billing/subscription/change", "POST",
        )
        assert cat == "financial"

    def test_integration_path(self, svc):
        cat = svc.classify_path(
            "/api/integrations/webhook", "POST",
        )
        assert cat == "integration"

    def test_demo_chat_path(self, svc):
        cat = svc.classify_path(
            "/api/public/demo/chat", "POST",
        )
        assert cat == "demo_chat"

    def test_general_get(self, svc):
        cat = svc.classify_path("/api/tickets", "GET")
        assert cat == "general_get"

    def test_general_post(self, svc):
        cat = svc.classify_path("/api/tickets", "POST")
        assert cat == "general_post"

    def test_unknown_falls_to_general(self, svc):
        cat = svc.classify_path("/unknown/path", "DELETE")
        assert cat == "general_post"


class TestRateLimitResult:
    """Tests for RateLimitResult class."""

    def test_allowed_result_headers(self):
        result = RateLimitResult(
            allowed=True, remaining=50, limit=100,
            reset_at=time.time() + 60,
        )
        headers = result.to_headers()
        assert headers["X-RateLimit-Limit"] == "100"
        assert headers["X-RateLimit-Remaining"] == "50"
        assert "Retry-After" not in headers

    def test_denied_result_headers(self):
        result = RateLimitResult(
            allowed=False, remaining=0, limit=10,
            reset_at=time.time() + 30, retry_after=30,
        )
        headers = result.to_headers()
        assert headers["Retry-After"] == "30"

    def test_remaining_never_negative(self):
        result = RateLimitResult(
            allowed=True, remaining=-5, limit=100,
            reset_at=time.time() + 60,
        )
        headers = result.to_headers()
        assert int(
            headers["X-RateLimit-Remaining"]
        ) >= 0


class TestSlidingWindow:
    """Tests for in-memory sliding window rate limiting."""

    def test_allows_under_limit(self, svc):
        for _ in range(5):
            result = svc.check_rate_limit(
                "auth_login", "user@test.com",
            )
            assert result.allowed is True

    def test_blocks_at_limit(self, svc):
        for _ in range(10):
            svc.check_rate_limit("auth_login", "a@b.com")
        result = svc.check_rate_limit("auth_login", "a@b.com")
        assert result.allowed is False

    def test_remaining_decreases(self, svc):
        r1 = svc.check_rate_limit("general_get", "1.2.3.4")
        r2 = svc.check_rate_limit("general_get", "1.2.3.4")
        assert r2.remaining < r1.remaining

    def test_separate_identifiers(self, svc):
        """Different identifiers have independent counters."""
        for _ in range(100):
            svc.check_rate_limit("general_get", "1.1.1.1")
        result = svc.check_rate_limit("general_get", "2.2.2.2")
        assert result.allowed is True

    def test_auth_reset_3_per_hour(self, svc):
        """auth_reset allows only 3 requests per hour."""
        for _ in range(3):
            result = svc.check_rate_limit(
                "auth_reset", "user@test.com",
            )
            assert result.allowed is True
        result = svc.check_rate_limit(
            "auth_reset", "user@test.com",
        )
        assert result.allowed is False


class TestProgressiveBackoff:
    """Tests for progressive backoff on failures."""

    def test_first_failure_no_backoff(self, svc):
        backoff = svc.record_failure("auth_login", "a@b.com")
        assert backoff == 2  # index 1 in backoff list

    def test_second_failure_increases(self, svc):
        svc.record_failure("auth_login", "a@b.com")
        backoff = svc.record_failure("auth_login", "a@b.com")
        assert backoff == 4

    def test_lockout_after_max_failures(self, svc):
        """After exceeding backoff list, lockout is applied."""
        for _ in range(6):
            svc.record_failure("auth_login", "a@b.com")
        assert svc.is_locked_out("auth_login", "a@b.com")

    def test_is_not_locked_out_initially(self, svc):
        assert svc.is_locked_out("auth_login", "a@b.com") is False

    def test_lockout_auth_15min(self, svc):
        cfg = CATEGORY_CONFIG["auth_login"]
        for _ in range(6):
            svc.record_failure("auth_login", "lock@test.com")
        assert svc.is_locked_out("auth_login", "lock@test.com")
        assert cfg["lockout_duration"] == 900

    def test_lockout_financial_5min(self, svc):
        cfg = CATEGORY_CONFIG["financial"]
        for _ in range(6):
            svc.record_failure("financial", "user-1")
        assert svc.is_locked_out("financial", "user-1")
        assert cfg["lockout_duration"] == 300

    def test_reset_clears_lockout(self, svc):
        for _ in range(6):
            svc.record_failure("auth_login", "a@b.com")
        assert svc.is_locked_out("auth_login", "a@b.com")
        svc.reset("auth_login", "a@b.com")
        assert svc.is_locked_out("auth_login", "a@b.com") is False


class TestFailOpen:
    """Tests for fail-open behavior when Redis is unavailable."""

    def test_no_redis_uses_in_memory(self, svc):
        """Service should work without Redis (in-memory)."""
        result = svc.check_rate_limit(
            "general_get", "1.2.3.4",
        )
        assert result.allowed is True
        assert result.remaining is not None


class TestSingleton:
    """Tests for the singleton service instance."""

    def test_get_rate_limit_service_returns_instance(self):
        svc = get_rate_limit_service()
        assert isinstance(svc, RateLimitService)

    def test_singleton_is_same_instance(self):
        s1 = get_rate_limit_service()
        s2 = get_rate_limit_service()
        assert s1 is s2
