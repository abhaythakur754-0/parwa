"""
Tests for PARWA Event Buffer (Day 5)

Tests:
- Event storage and retrieval
- 24h TTL on events (BC-005)
- Tenant-scoped events (BC-001)
- Events since timestamp (reconnection recovery, BC-005)
- Cleanup of old events
- Fail-open on Redis errors (BC-012)
- Max events per query cap
"""

import json
import time
from unittest.mock import AsyncMock, patch

import pytest

from backend.app.core.event_buffer import (
    EVENT_BUFFER_TTL_SECONDS,
    MAX_EVENTS_PER_QUERY,
    cleanup_old_events,
    get_buffer_stats,
    get_events_since,
    store_event,
)


class TestStoreEvent:
    """Test event buffer storage (BC-005, BC-001)."""

    @pytest.mark.asyncio
    async def test_store_success(self):
        """store_event stores event in Redis sorted set."""
        mock_redis = AsyncMock()
        mock_redis.zadd = AsyncMock(return_value=True)
        mock_redis.expire = AsyncMock(return_value=True)
        with patch("backend.app.core.event_buffer.get_redis", return_value=mock_redis):
            result = await store_event(
                company_id="acme",
                event_type="ticket:new",
                payload={"ticket_id": "123"},
            )
            assert result is True
            mock_redis.zadd.assert_called_once()
            mock_redis.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_uses_correct_key(self):
        """store_event uses tenant-scoped Redis key (BC-001)."""
        mock_redis = AsyncMock()
        with patch("backend.app.core.event_buffer.get_redis", return_value=mock_redis):
            await store_event("acme", "test", {})
            key = mock_redis.zadd.call_args[0][0]
            assert key == "parwa:acme:events"

    @pytest.mark.asyncio
    async def test_store_sets_ttl(self):
        """store_event sets 24h TTL on the key (BC-005)."""
        mock_redis = AsyncMock()
        with patch("backend.app.core.event_buffer.get_redis", return_value=mock_redis):
            await store_event("acme", "test", {})
            mock_redis.expire.assert_called_once_with(
                "parwa:acme:events",
                EVENT_BUFFER_TTL_SECONDS,
            )

    @pytest.mark.asyncio
    async def test_store_event_record_format(self):
        """store_event stores valid JSON event record."""
        mock_redis = AsyncMock()
        with patch("backend.app.core.event_buffer.get_redis", return_value=mock_redis):
            await store_event("acme", "ticket:new", {"id": "123"})
            # Get the stored data from zadd call
            call_args = mock_redis.zadd.call_args
            data_dict = call_args[0][1]  # {json_string: score}
            stored_json = list(data_dict.keys())[0]
            event = json.loads(stored_json)
            assert event["event_type"] == "ticket:new"
            assert event["payload"] == {"id": "123"}
            assert "created_at" in event
            assert "timestamp" in event

    @pytest.mark.asyncio
    async def test_store_fail_open(self):
        """store_event returns False on Redis error (BC-012)."""
        mock_redis = AsyncMock()
        mock_redis.zadd = AsyncMock(side_effect=Exception("Redis down"))
        with patch("backend.app.core.event_buffer.get_redis", return_value=mock_redis):
            result = await store_event("acme", "test", {})
            assert result is False


class TestGetEventsSince:
    """Test event retrieval for reconnection recovery (BC-005)."""

    @pytest.mark.asyncio
    async def test_get_events_empty_buffer(self):
        """get_events_since returns empty list when no events."""
        mock_redis = AsyncMock()
        mock_redis.zrangebyscore = AsyncMock(return_value=[])
        with patch("backend.app.core.event_buffer.get_redis", return_value=mock_redis):
            result = await get_events_since("acme", last_seen=0.0)
            assert result == []

    @pytest.mark.asyncio
    async def test_get_events_returns_stored_events(self):
        """get_events_since returns events after the given timestamp."""
        now = time.time()
        event_data = json.dumps({
            "event_type": "ticket:new",
            "payload": {"id": "456"},
            "created_at": "2025-01-01T00:00:00Z",
            "timestamp": now + 1,
        })
        mock_redis = AsyncMock()
        mock_redis.zrangebyscore = AsyncMock(return_value=[event_data])
        with patch("backend.app.core.event_buffer.get_redis", return_value=mock_redis):
            result = await get_events_since("acme", last_seen=now)
            assert len(result) == 1
            assert result[0]["event_type"] == "ticket:new"
            assert result[0]["payload"]["id"] == "456"

    @pytest.mark.asyncio
    async def test_get_events_uses_open_interval(self):
        """get_events_since uses open interval (excludes exact match)."""
        mock_redis = AsyncMock()
        mock_redis.zrangebyscore = AsyncMock(return_value=[])
        with patch("backend.app.core.event_buffer.get_redis", return_value=mock_redis):
            await get_events_since("acme", last_seen=1000.0)
            # Verify the open interval syntax
            call_args = mock_redis.zrangebyscore.call_args
            assert call_args[0][1] == "(1000.0"  # Open interval

    @pytest.mark.asyncio
    async def test_get_events_defaults_to_all(self):
        """get_events_since with last_seen=None returns all events."""
        mock_redis = AsyncMock()
        mock_redis.zrangebyscore = AsyncMock(return_value=[])
        with patch("backend.app.core.event_buffer.get_redis", return_value=mock_redis):
            await get_events_since("acme", last_seen=None)
            call_args = mock_redis.zrangebyscore.call_args
            assert call_args[0][1] == "(0.0"

    @pytest.mark.asyncio
    async def test_get_events_capped_at_max(self):
        """get_events_since caps results at MAX_EVENTS_PER_QUERY."""
        mock_redis = AsyncMock()
        mock_redis.zrangebyscore = AsyncMock(return_value=[])
        with patch("backend.app.core.event_buffer.get_redis", return_value=mock_redis):
            await get_events_since("acme", last_seen=0.0, limit=9999)
            call_kwargs = mock_redis.zrangebyscore.call_args
            assert call_kwargs[1]["num"] == MAX_EVENTS_PER_QUERY

    @pytest.mark.asyncio
    async def test_get_events_tenant_scoped(self):
        """get_events_since uses tenant-scoped key (BC-001)."""
        mock_redis = AsyncMock()
        mock_redis.zrangebyscore = AsyncMock(return_value=[])
        with patch("backend.app.core.event_buffer.get_redis", return_value=mock_redis):
            await get_events_since("acme", last_seen=0.0)
            key = mock_redis.zrangebyscore.call_args[0][0]
            assert key == "parwa:acme:events"

    @pytest.mark.asyncio
    async def test_get_events_fail_open(self):
        """get_events_since returns empty on Redis error (BC-012)."""
        mock_redis = AsyncMock()
        mock_redis.zrangebyscore = AsyncMock(
            side_effect=Exception("Redis down")
        )
        with patch("backend.app.core.event_buffer.get_redis", return_value=mock_redis):
            result = await get_events_since("acme", last_seen=0.0)
            assert result == []

    @pytest.mark.asyncio
    async def test_get_events_skips_malformed_json(self):
        """get_events_since skips malformed JSON entries."""
        mock_redis = AsyncMock()
        # Mix valid and invalid entries
        valid = json.dumps({
            "event_type": "test",
            "payload": {},
            "created_at": "2025-01-01",
            "timestamp": 1000.0,
        })
        mock_redis.zrangebyscore = AsyncMock(return_value=[
            "not json",
            valid,
            "also not json",
            "{broken json",
        ])
        with patch("backend.app.core.event_buffer.get_redis", return_value=mock_redis):
            result = await get_events_since("acme", last_seen=0.0)
            assert len(result) == 1
            assert result[0]["event_type"] == "test"


class TestCleanupOldEvents:
    """Test event buffer cleanup (BC-005: 24h retention)."""

    @pytest.mark.asyncio
    async def test_cleanup_removes_old_events(self):
        """cleanup_old_events removes events older than 24h."""
        mock_redis = AsyncMock()
        mock_redis.zremrangebyscore = AsyncMock(return_value=5)
        with patch("backend.app.core.event_buffer.get_redis", return_value=mock_redis):
            removed = await cleanup_old_events("acme")
            assert removed == 5

    @pytest.mark.asyncio
    async def test_cleanup_uses_correct_cutoff(self):
        """cleanup_old_events uses open interval (excludes exact 24h)."""
        mock_redis = AsyncMock()
        mock_redis.zremrangebyscore = AsyncMock(return_value=0)
        with patch("backend.app.core.event_buffer.get_redis", return_value=mock_redis):
            await cleanup_old_events("acme")
            call_args = mock_redis.zremrangebyscore.call_args
            # Upper bound should be open interval (excluded)
            assert call_args[0][1] == "-inf"
            assert "( " in call_args[0][2] or call_args[0][2].startswith("(")

    @pytest.mark.asyncio
    async def test_cleanup_fail_open(self):
        """cleanup_old_events returns 0 on Redis error."""
        mock_redis = AsyncMock()
        mock_redis.zremrangebyscore = AsyncMock(
            side_effect=Exception("Redis down")
        )
        with patch("backend.app.core.event_buffer.get_redis", return_value=mock_redis):
            removed = await cleanup_old_events("acme")
            assert removed == 0


class TestGetBufferStats:
    """Test event buffer statistics."""

    @pytest.mark.asyncio
    async def test_empty_buffer_stats(self):
        """Buffer stats return zeros for empty buffer."""
        mock_redis = AsyncMock()
        mock_redis.zcard = AsyncMock(return_value=0)
        with patch("backend.app.core.event_buffer.get_redis", return_value=mock_redis):
            stats = await get_buffer_stats("acme")
            assert stats["total_events"] == 0
            assert stats["oldest_event_age_hours"] is None
            assert stats["newest_event_age_hours"] is None

    @pytest.mark.asyncio
    async def test_buffer_stats_with_events(self):
        """Buffer stats return counts and ages for non-empty buffer."""
        now = time.time()
        old_event = json.dumps({
            "event_type": "old",
            "payload": {},
            "created_at": "2025-01-01",
            "timestamp": now - 7200,  # 2 hours ago
        })
        new_event = json.dumps({
            "event_type": "new",
            "payload": {},
            "created_at": "2025-01-01",
            "timestamp": now - 60,  # 1 min ago
        })
        mock_redis = AsyncMock()
        mock_redis.zcard = AsyncMock(return_value=2)
        mock_redis.zrange = AsyncMock(side_effect=[
            [old_event],   # oldest (index 0)
            [new_event],   # newest (index -1)
        ])
        with patch("backend.app.core.event_buffer.get_redis", return_value=mock_redis):
            stats = await get_buffer_stats("acme")
            assert stats["total_events"] == 2
            assert stats["oldest_event_age_hours"] is not None
            assert stats["newest_event_age_hours"] is not None
            # Newest should be newer than oldest
            assert stats["newest_event_age_hours"] < stats["oldest_event_age_hours"]

    @pytest.mark.asyncio
    async def test_stats_fail_open(self):
        """Buffer stats return zeros on Redis error."""
        mock_redis = AsyncMock()
        mock_redis.zcard = AsyncMock(side_effect=Exception("Redis down"))
        with patch("backend.app.core.event_buffer.get_redis", return_value=mock_redis):
            stats = await get_buffer_stats("acme")
            assert stats["total_events"] == 0


class TestTTLConstants:
    """Test that TTL constants are correct per BC-005."""

    def test_event_buffer_ttl_is_24_hours(self):
        """Event buffer TTL is 86400 seconds (24h) per BC-005."""
        assert EVENT_BUFFER_TTL_SECONDS == 86400

    def test_max_events_per_query_has_limit(self):
        """Max events per query has a reasonable cap."""
        assert MAX_EVENTS_PER_QUERY == 500
        assert MAX_EVENTS_PER_QUERY <= 1000
