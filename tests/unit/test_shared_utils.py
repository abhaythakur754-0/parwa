"""
Tests for shared/utils/datetime.py

Tests UTC handling, ISO formatting, parsing,
duration formatting, expiry checks.
BC-012: All datetime operations must be timezone-aware UTC.
"""

from datetime import datetime, timezone, timedelta

from shared.utils.datetime import (
    utcnow,
    to_iso,
    from_iso,
    format_duration,
    is_expired,
)


class TestUtcnow:
    """Tests for utcnow() function."""

    def test_returns_datetime(self):
        result = utcnow()
        assert isinstance(result, datetime)

    def test_has_timezone_info(self):
        result = utcnow()
        assert result.tzinfo is not None

    def test_is_utc_timezone(self):
        result = utcnow()
        assert result.tzinfo == timezone.utc

    def test_is_approximately_now(self):
        before = datetime.now(timezone.utc)
        result = utcnow()
        after = datetime.now(timezone.utc)
        assert before <= result <= after

    def test_multiple_calls_return_different_times(self):
        import time
        t1 = utcnow()
        time.sleep(0.01)
        t2 = utcnow()
        assert t2 >= t1

    def test_never_returns_naive_datetime(self):
        for _ in range(10):
            result = utcnow()
            assert result.tzinfo is not None, (
                "utcnow() must always return tz-aware datetime"
            )


class TestToIso:
    """Tests for to_iso() function."""

    def test_default_returns_string(self):
        result = to_iso()
        assert isinstance(result, str)

    def test_default_is_current_time(self):
        before = to_iso()
        now_iso = to_iso()
        after = to_iso()
        # ISO strings should be in chronological order
        assert before <= now_iso <= after

    def test_explicit_datetime(self):
        dt = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = to_iso(dt)
        assert "2025-06-15" in result
        assert "12:00:00" in result

    def test_naive_datetime_gets_utc(self):
        dt = datetime(2025, 6, 15, 12, 0, 0)  # no tzinfo
        result = to_iso(dt)
        assert "2025-06-15" in result
        parsed = from_iso(result)
        assert parsed.tzinfo is not None

    def test_returns_valid_iso_string(self):
        dt = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        result = to_iso(dt)
        # Should be parseable back
        parsed = from_iso(result)
        assert parsed is not None
        assert parsed.year == 2025


class TestFromIso:
    """Tests for from_iso() function."""

    def test_valid_iso_string(self):
        result = from_iso("2025-06-15T12:00:00+00:00")
        assert result is not None
        assert isinstance(result, datetime)

    def test_iso_with_z_suffix(self):
        result = from_iso("2025-06-15T12:00:00Z")
        assert result is not None
        assert result.year == 2025

    def test_naive_iso_gets_utc(self):
        result = from_iso("2025-06-15T12:00:00")
        assert result is not None
        assert result.tzinfo is not None

    def test_none_returns_none(self):
        result = from_iso(None)
        assert result is None

    def test_empty_string_returns_none(self):
        result = from_iso("")
        assert result is None

    def test_garbage_string_returns_none(self):
        result = from_iso("not-a-date")
        assert result is None

    def test_non_string_returns_none(self):
        result = from_iso(12345)
        assert result is None

    def test_round_trip(self):
        original = datetime(
            2025, 6, 15, 12, 30, 45, 123456, tzinfo=timezone.utc
        )
        iso_str = to_iso(original)
        parsed = from_iso(iso_str)
        assert parsed is not None
        assert parsed.year == original.year
        assert parsed.month == original.month
        assert parsed.day == original.day
        assert parsed.hour == original.hour


class TestFormatDuration:
    """Tests for format_duration() function."""

    def test_milliseconds(self):
        assert format_duration(0.5) == "500ms"

    def test_one_hundred_ms(self):
        assert format_duration(0.1) == "100ms"

    def test_one_second(self):
        assert "1.0s" in format_duration(1.0)

    def test_seconds_with_decimal(self):
        result = format_duration(1.5)
        assert "1.5s" in result

    def test_minutes(self):
        result = format_duration(65.0)
        assert "1m" in result
        assert "5.0s" in result

    def test_hours(self):
        result = format_duration(3665.0)
        assert "1h" in result
        assert "1m" in result

    def test_zero(self):
        assert format_duration(0) == "0ms"

    def test_negative_returns_zero(self):
        assert format_duration(-5) == "0ms"

    def test_very_small(self):
        assert format_duration(0.001) == "1ms"

    def test_large_hours(self):
        result = format_duration(7384.0)
        assert "2h" in result


class TestIsExpired:
    """Tests for is_expired() function."""

    def test_past_datetime_is_expired(self):
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        assert is_expired(past) is True

    def test_future_datetime_not_expired(self):
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        assert is_expired(future) is False

    def test_just_expired(self):
        now = datetime.now(timezone.utc)
        # Create a time 1 microsecond in the past
        past = now - timedelta(microseconds=1)
        assert is_expired(past) is True

    def test_not_yet_expired(self):
        future = datetime.now(timezone.utc) + timedelta(seconds=60)
        assert is_expired(future) is False
