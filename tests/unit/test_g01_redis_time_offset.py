"""
Tests for G01: Rate limiter uses Redis time offset consistently.

Tests that record_failure, is_locked_out, and check_rate_limit
all use the same _now() method with Redis time offset.
"""

import time

from backend.app.services.rate_limit_service import (
    CATEGORY_CONFIG,
    RateLimitService,
)


class TestRedisTimeOffset:
    """Tests for G01: Redis TIME offset consistency."""

    def test_now_uses_offset(self):
        """_now() returns time.time() + offset."""
        svc = RateLimitService()
        svc._redis_time_offset = 10.0
        base = time.time()
        now = svc._now()
        # Allow 1s drift for execution time
        assert abs((now - base) - 10.0) < 1.0

    def test_now_zero_offset(self):
        """_now() with zero offset equals time.time()."""
        svc = RateLimitService()
        svc._redis_time_offset = 0
        base = time.time()
        now = svc._now()
        assert abs(now - base) < 1.0

    def test_negative_offset(self):
        """_now() works with negative offset (Redis behind local)."""
        svc = RateLimitService()
        svc._redis_time_offset = -5.0
        base = time.time()
        now = svc._now()
        assert abs((now - base) - (-5.0)) < 1.0

    def test_record_failure_uses_offset(self):
        """record_failure uses _now() with offset."""
        svc = RateLimitService()
        svc._redis_time_offset = 3600.0  # 1 hour ahead

        backoff = svc.record_failure("auth_login", "a@b.com")
        assert backoff is not None

        # The failure timestamp should be ~1 hour in the future
        fail_key = svc._make_failure_key("auth_login", "a@b.com")
        info = svc._failures.get(fail_key)
        assert info is not None
        assert info["last_fail"] > time.time() + 3500

    def test_is_locked_out_uses_offset(self):
        """is_locked_out uses _now() with offset for timing."""
        svc = RateLimitService()
        svc._redis_time_offset = 0

        # Not locked out initially
        assert svc.is_locked_out("auth_login", "a@b.com") is False

        # Lock out
        for _ in range(6):
            svc.record_failure("auth_login", "lock@b.com")
        assert svc.is_locked_out("auth_login", "lock@b.com") is True

    def test_check_rate_limit_uses_offset(self):
        """check_rate_limit uses _now() with offset for windows."""
        svc = RateLimitService()
        svc._redis_time_offset = 0

        result = svc.check_rate_limit("auth_login", "test@test.com")
        assert result.allowed is True

    def test_sync_redis_time_sets_offset(self):
        """sync_redis_time computes correct offset."""
        svc = RateLimitService()

        # Mock redis.time() to return a known value
        mock_redis = type("MockRedis", (), {})()
        # redis.time() returns (seconds, microseconds)
        redis_seconds = int(time.time()) + 30
        mock_redis.time = lambda: (redis_seconds, 500000)
        svc._redis = mock_redis

        import asyncio
        asyncio.get_event_loop().run_until_complete(
            svc.sync_redis_time()
        )

        # Offset should be approximately 30 seconds
        assert abs(svc._redis_time_offset - 30.0) < 1.0

    def test_sync_redis_time_no_redis(self):
        """sync_redis_time is no-op when no Redis client."""
        svc = RateLimitService()  # no redis client
        import asyncio
        asyncio.get_event_loop().run_until_complete(
            svc.sync_redis_time()
        )
        assert svc._redis_time_offset == 0

    def test_sync_redis_time_exception_fails_gracefully(self):
        """sync_redis_time handles Redis errors gracefully."""
        svc = RateLimitService()
        mock_redis = type("MockRedis", (), {})()
        mock_redis.time = lambda: (_ for _ in ()).throw(
            Exception("Connection refused")
        )
        svc._redis = mock_redis

        import asyncio
        asyncio.get_event_loop().run_until_complete(
            svc.sync_redis_time()
        )
        # Should not crash, offset stays at 0
        assert svc._redis_time_offset == 0

    def test_lockout_expiry_uses_offset(self):
        """Lockout expiry uses _now() with offset."""
        svc = RateLimitService()
        svc._redis_time_offset = 0

        # Trigger lockout
        for _ in range(6):
            svc.record_failure("financial", "user-1")

        assert svc.is_locked_out("financial", "user-1") is True

        # Simulate time passing by advancing offset
        lockout_dur = CATEGORY_CONFIG["financial"]["lockout_duration"]
        svc._redis_time_offset = lockout_dur + 1

        # Should be unlocked now
        assert svc.is_locked_out("financial", "user-1") is False

    def test_all_time_methods_use_same_source(self):
        """All time-dependent methods use _now() consistently."""
        svc = RateLimitService()
        offset = 42.0
        svc._redis_time_offset = offset

        # record_failure
        svc.record_failure("auth_login", "consistency@test.com")
        fail_key = svc._make_failure_key(
            "auth_login", "consistency@test.com"
        )
        info = svc._failures.get(fail_key)
        assert info is not None

        # The recorded time should be approximately offset ahead
        expected_min = time.time() + offset - 1
        assert info["last_fail"] >= expected_min

        # check_rate_limit should also use offset
        result = svc.check_rate_limit(
            "auth_login", "consistency@test.com"
        )
        assert result.reset_at >= expected_min + 60


class TestAuthPhoneCategory:
    """Tests for auth_phone_send and auth_phone_verify rate limit categories."""

    def test_auth_phone_send_config(self):
        """auth_phone_send category has correct config."""
        cfg = CATEGORY_CONFIG["auth_phone_send"]
        assert cfg["limit"] == 5
        assert cfg["window"] == 300
        assert cfg["scope"] == "ip"
        assert cfg["lockout_duration"] == 900

    def test_auth_phone_verify_config(self):
        """auth_phone_verify category has correct config."""
        cfg = CATEGORY_CONFIG["auth_phone_verify"]
        assert cfg["limit"] == 20
        assert cfg["window"] == 300
        assert cfg["scope"] == "ip"
        assert cfg["lockout_duration"] == 300

    def test_classify_phone_send(self):
        """Phone send endpoint classified as auth_phone_send."""
        svc = RateLimitService()
        cat = svc.classify_path(
            "/api/auth/phone/send", "POST"
        )
        assert cat == "auth_phone_send"

    def test_classify_phone_verify(self):
        """Phone verify endpoint classified as auth_phone_verify."""
        svc = RateLimitService()
        cat = svc.classify_path(
            "/api/auth/phone/verify", "POST"
        )
        assert cat == "auth_phone_verify"

    def test_phone_send_rate_limit_5_per_5min(self):
        """auth_phone_send allows only 5 requests per 5 minutes."""
        svc = RateLimitService()
        svc._redis_time_offset = 0

        for _ in range(5):
            result = svc.check_rate_limit(
                "auth_phone_send", "1.2.3.4"
            )
            assert result.allowed is True

        result = svc.check_rate_limit(
            "auth_phone_send", "1.2.3.4"
        )
        assert result.allowed is False

    def test_phone_verify_rate_limit_20_per_5min(self):
        """auth_phone_verify allows 20 requests per 5 minutes."""
        svc = RateLimitService()
        svc._redis_time_offset = 0

        for _ in range(20):
            result = svc.check_rate_limit(
                "auth_phone_verify", "1.2.3.4"
            )
            assert result.allowed is True

        result = svc.check_rate_limit(
            "auth_phone_verify", "1.2.3.4"
        )
        assert result.allowed is False

    def test_phone_separate_identifiers(self):
        """Different IPs have separate rate limit counters."""
        svc = RateLimitService()
        svc._redis_time_offset = 0

        for _ in range(5):
            svc.check_rate_limit(
                "auth_phone_send", "1.1.1.1"
            )

        # Different IP should still be allowed
        result = svc.check_rate_limit(
            "auth_phone_send", "2.2.2.2"
        )
        assert result.allowed is True
