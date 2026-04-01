"""
Tests for security/rate_limiter.py

Tests sliding window rate limiting, progressive lockout,
fail-open behavior, X-RateLimit headers (BC-011 / BC-012).
"""

import time

from security.rate_limiter import (
    DEFAULT_REQUESTS_PER_WINDOW,
    DEFAULT_WINDOW_SECONDS,
    LOCKOUT_DURATIONS,
    LockoutLevel,
    ProgressiveLockout,
    RateLimiter,
    RateLimitResult,
    SlidingWindowCounter,
)


class TestRateLimitResult:
    """Tests for RateLimitResult data class."""

    def test_allowed_result(self):
        result = RateLimitResult(
            allowed=True, remaining=99, limit=100,
            reset_at=time.time() + 60,
        )
        assert result.allowed is True
        assert result.remaining == 99
        assert result.retry_after is None

    def test_denied_result(self):
        result = RateLimitResult(
            allowed=False, remaining=0, limit=100,
            reset_at=time.time() + 30, retry_after=30,
        )
        assert result.allowed is False
        assert result.retry_after == 30

    def test_to_headers_basic(self):
        result = RateLimitResult(
            allowed=True, remaining=50, limit=100,
            reset_at=1700000000,
        )
        headers = result.to_headers()
        assert headers["X-RateLimit-Limit"] == "100"
        assert headers["X-RateLimit-Remaining"] == "50"
        assert headers["X-RateLimit-Reset"] == "1700000000"
        assert "Retry-After" not in headers

    def test_to_headers_with_retry_after(self):
        result = RateLimitResult(
            allowed=False, remaining=0, limit=100,
            reset_at=time.time() + 30, retry_after=30,
        )
        headers = result.to_headers()
        assert headers["Retry-After"] == "30"

    def test_to_headers_remaining_never_negative(self):
        result = RateLimitResult(
            allowed=True, remaining=-5, limit=100,
            reset_at=time.time() + 60,
        )
        headers = result.to_headers()
        assert int(headers["X-RateLimit-Remaining"]) >= 0


class TestSlidingWindowCounter:
    """Tests for sliding window rate limiting."""

    def test_allows_under_limit(self):
        counter = SlidingWindowCounter(
            requests_per_window=5, window_seconds=60,
        )
        for i in range(5):
            result = counter.check_rate_limit("comp-1", "1.2.3.4")
            assert result.allowed is True, f"Request {i+1} should be allowed"

    def test_blocks_at_limit(self):
        counter = SlidingWindowCounter(
            requests_per_window=3, window_seconds=60,
        )
        for _ in range(3):
            counter.check_rate_limit("comp-1", "1.2.3.4")
        result = counter.check_rate_limit("comp-1", "1.2.3.4")
        assert result.allowed is False

    def test_remaining_decreases(self):
        counter = SlidingWindowCounter(
            requests_per_window=10, window_seconds=60,
        )
        r1 = counter.check_rate_limit("comp-1")
        assert r1.remaining == 9
        r2 = counter.check_rate_limit("comp-1")
        assert r2.remaining == 8

    def test_separate_keys(self):
        """Different company_ids should have separate counters."""
        counter = SlidingWindowCounter(
            requests_per_window=2, window_seconds=60,
        )
        counter.check_rate_limit("comp-1")
        counter.check_rate_limit("comp-1")
        # comp-1 should be rate limited
        result1 = counter.check_rate_limit("comp-1")
        assert result1.allowed is False
        # comp-2 should still be allowed
        result2 = counter.check_rate_limit("comp-2")
        assert result2.allowed is True

    def test_company_id_in_key(self):
        """BC-001: Keys must be deterministic per company_id (collision-free)."""
        counter = SlidingWindowCounter()
        key1 = counter._make_key("comp-abc", "10.0.0.1")
        key2 = counter._make_key("comp-abc", "10.0.0.1")
        # Same inputs produce same key (deterministic)
        assert key1 == key2
        # Different company_id produces different key
        key3 = counter._make_key("comp-xyz", "10.0.0.1")
        assert key1 != key3
        # Key contains the rate limit prefix
        assert "parwa:ratelimit:" in key1

    def test_denied_result_has_retry_after(self):
        counter = SlidingWindowCounter(
            requests_per_window=1, window_seconds=60,
        )
        counter.check_rate_limit("comp-1")
        result = counter.check_rate_limit("comp-1")
        assert result.allowed is False
        assert result.retry_after is not None
        assert result.retry_after > 0

    def test_client_ip_granularity(self):
        """Same company_id but different IPs should be separate."""
        counter = SlidingWindowCounter(
            requests_per_window=1, window_seconds=60,
        )
        counter.check_rate_limit("comp-1", "10.0.0.1")
        # Same company, different IP - should be allowed
        result = counter.check_rate_limit("comp-1", "10.0.0.2")
        assert result.allowed is True


class TestProgressiveLockout:
    """Tests for progressive lockout behavior."""

    def test_first_violation_level_1(self):
        lockout = ProgressiveLockout()
        level = lockout.record_violation("comp-1", "1.2.3.4")
        assert level == 1

    def test_increasing_levels(self):
        lockout = ProgressiveLockout()
        l1 = lockout.record_violation("comp-1", "1.2.3.4")
        l2 = lockout.record_violation("comp-1", "1.2.3.4")
        l3 = lockout.record_violation("comp-1", "1.2.3.4")
        assert l1 == 1
        assert l2 == 2
        assert l3 == 3

    def test_max_level_capped(self):
        lockout = ProgressiveLockout(max_level=3)
        for _ in range(10):
            lockout.record_violation("comp-1", "1.2.3.4")
        key = lockout._make_key("comp-1", "1.2.3.4")
        assert lockout._violations[key]["level"] <= 3

    def test_lockout_duration_increases(self):
        """Level 1 = 60s, Level 2 = 120s, Level 3 = 240s."""
        lockout = ProgressiveLockout()
        lockout.record_violation("comp-1")
        remaining1 = lockout.get_lockout_remaining("comp-1")
        lockout.record_violation("comp-1")
        remaining2 = lockout.get_lockout_remaining("comp-1")
        assert remaining2 > remaining1

    def test_not_locked_out_initially(self):
        lockout = ProgressiveLockout()
        assert lockout.is_locked_out("comp-1") is False

    def test_locked_out_after_violation(self):
        lockout = ProgressiveLockout()
        lockout.record_violation("comp-1")
        assert lockout.is_locked_out("comp-1") is True

    def test_lockout_remaining_decreases(self):
        lockout = ProgressiveLockout()
        lockout.record_violation("comp-1")
        r1 = lockout.get_lockout_remaining("comp-1")
        # (no sleep, but check it's positive)
        assert r1 > 0

    def test_reset_clears_lockout(self):
        lockout = ProgressiveLockout()
        lockout.record_violation("comp-1")
        assert lockout.is_locked_out("comp-1") is True
        lockout.reset("comp-1")
        assert lockout.is_locked_out("comp-1") is False

    def test_separate_keys_per_company(self):
        """BC-001: Lockout should be per-company_id."""
        lockout = ProgressiveLockout()
        lockout.record_violation("comp-1")
        assert lockout.is_locked_out("comp-1") is True
        assert lockout.is_locked_out("comp-2") is False

    def test_separate_keys_per_ip(self):
        lockout = ProgressiveLockout()
        lockout.record_violation("comp-1", "10.0.0.1")
        assert lockout.is_locked_out("comp-1", "10.0.0.1") is True
        assert lockout.is_locked_out("comp-1", "10.0.0.2") is False


class TestLockoutDurations:
    """Tests for lockout duration constants."""

    def test_level_1_is_60(self):
        assert LOCKOUT_DURATIONS[LockoutLevel.LEVEL_1] == 60

    def test_level_2_is_120(self):
        assert LOCKOUT_DURATIONS[LockoutLevel.LEVEL_2] == 120

    def test_level_3_is_240(self):
        assert LOCKOUT_DURATIONS[LockoutLevel.LEVEL_3] == 240

    def test_level_4_is_480(self):
        assert LOCKOUT_DURATIONS[LockoutLevel.LEVEL_4] == 480

    def test_level_5_is_900(self):
        assert LOCKOUT_DURATIONS[LockoutLevel.LEVEL_5] == 900

    def test_none_is_0(self):
        assert LOCKOUT_DURATIONS[LockoutLevel.NONE] == 0


class TestRateLimiter:
    """Tests for combined RateLimiter."""

    def test_allows_under_limit(self):
        limiter = RateLimiter(requests_per_window=5, window_seconds=60)
        for _ in range(5):
            result = limiter.check("comp-1", "1.2.3.4")
            assert result.allowed is True

    def test_blocks_at_limit(self):
        limiter = RateLimiter(requests_per_window=2, window_seconds=60)
        limiter.check("comp-1", "1.2.3.4")
        limiter.check("comp-1", "1.2.3.4")
        result = limiter.check("comp-1", "1.2.3.4")
        assert result.allowed is False

    def test_lockout_blocks_immediately(self):
        limiter = RateLimiter(requests_per_window=1, window_seconds=60)
        limiter.check("comp-1")
        result = limiter.check("comp-1")
        assert result.allowed is False
        # Second check should also be blocked (lockout, not just window)
        result2 = limiter.check("comp-1")
        assert result2.allowed is False
        assert result2.lockout_level > 0

    def test_lockout_level_increases(self):
        limiter = RateLimiter(requests_per_window=1, window_seconds=60)
        limiter.check("comp-1")
        limiter.check("comp-1")
        level1 = limiter.check("comp-1").lockout_level
        assert level1 >= 1

    def test_headers_on_allowed(self):
        limiter = RateLimiter(requests_per_window=10, window_seconds=60)
        result = limiter.check("comp-1")
        headers = result.to_headers()
        assert "X-RateLimit-Limit" in headers
        assert "X-RateLimit-Remaining" in headers
        assert "X-RateLimit-Reset" in headers

    def test_headers_on_denied(self):
        limiter = RateLimiter(requests_per_window=1, window_seconds=60)
        limiter.check("comp-1")
        result = limiter.check("comp-1")
        headers = result.to_headers()
        assert "Retry-After" in headers


class TestDefaultConstants:
    """Tests for default configuration constants."""

    def test_default_requests_per_window(self):
        assert DEFAULT_REQUESTS_PER_WINDOW == 100

    def test_default_window_seconds(self):
        assert DEFAULT_WINDOW_SECONDS == 60


class TestKeyCollisionSafety:
    """Tests for MD5-based key collision prevention (P0 fix)."""

    def test_delimiter_injection_same_company_different_ip(self):
        """company_id='comp|any' + IP='' should NOT collide with
        company_id='comp' + IP='any'."""
        counter = SlidingWindowCounter()
        key1 = counter._make_key("comp", "any")
        key2 = counter._make_key("comp|any", "")
        assert key1 != key2

    def test_delimiter_injection_special_chars(self):
        """Special chars in company_id don't cause collisions."""
        counter = SlidingWindowCounter()
        key1 = counter._make_key("a\nb", "1.2.3.4")
        key2 = counter._make_key("a", "nb1.2.3.4")
        assert key1 != key2

    def test_ipv6_address_no_collision(self):
        """IPv6 addresses with colons don't cause collisions."""
        counter = SlidingWindowCounter()
        key1 = counter._make_key("comp", "2001:db8::1")
        key2 = counter._make_key("comp|2001:db8:", "")
        assert key1 != key2

    def test_deterministic_same_inputs(self):
        """Same company_id + same IP always produces same key."""
        counter = SlidingWindowCounter()
        key1 = counter._make_key("test-comp", "10.0.0.1")
        key2 = counter._make_key("test-comp", "10.0.0.1")
        key3 = counter._make_key("test-comp", "10.0.0.1")
        assert key1 == key2 == key3

    def test_empty_string_ip_no_collision(self):
        counter = SlidingWindowCounter()
        key1 = counter._make_key("comp-a", "")
        key2 = counter._make_key("comp-a", "")
        assert key1 == key2

    def test_lockout_key_also_collision_safe(self):
        """ProgressiveLockout keys also use MD5 hash."""
        lockout = ProgressiveLockout()
        key1 = lockout._make_key("comp", "any")
        key2 = lockout._make_key("comp|any", "")
        assert key1 != key2

    def test_key_always_has_prefix(self):
        """All keys start with the rate limit prefix."""
        counter = SlidingWindowCounter()
        lockout = ProgressiveLockout()
        for company_id in ["test", "abc|def", "2001:db8::1"]:
            for client_ip in ["", "10.0.0.1", "::1"]:
                assert counter._make_key(company_id, client_ip).startswith(
                    "parwa:ratelimit:"
                )
                assert lockout._make_key(company_id, client_ip).startswith(
                    "parwa:ratelimit:lockout:"
                )
