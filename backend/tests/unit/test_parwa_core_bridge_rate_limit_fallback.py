"""The Python rate-limiter fallback must enforce the same sliding window as Rust."""

from app.core import parwa_core_bridge


def test_python_fallback_enforces_sliding_window_and_reset(monkeypatch):
    now = [1_000.0]
    monkeypatch.setattr(parwa_core_bridge.time, "time", lambda: now[0])
    limiter = parwa_core_bridge._RateLimiterBridge()
    limiter._rust = None  # Exercise the production SKIP_RUST_BUILD path.

    for expected_remaining in (4, 3, 2, 1, 0):
        result = limiter.check_rate_limit("auth_login", "user@example.com")
        assert result.allowed is True
        assert result.remaining == expected_remaining

    blocked = limiter.check_rate_limit("auth_login", "user@example.com")
    assert blocked.allowed is False
    assert blocked.remaining == 0
    assert blocked.retry_after == 60

    # Another identifier has an independent bucket.
    assert limiter.check_rate_limit("auth_login", "other@example.com").allowed is True

    # Expire the first request window and verify requests are admitted again.
    now[0] += 61
    assert limiter.check_rate_limit("auth_login", "user@example.com").allowed is True

    limiter.reset("auth_login", "user@example.com")
    assert limiter.check_rate_limit("auth_login", "user@example.com").remaining == 4
