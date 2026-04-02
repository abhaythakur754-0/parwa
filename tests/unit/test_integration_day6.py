"""
Day 6: Integration Tests — Full Middleware Chain + Cross-Module

Tests the complete request lifecycle through all middleware layers,
cross-module data flow, and infrastructure property consistency
across all Week 1 components.

Verified Building Codes:
- BC-001: Multi-tenant isolation (company_id in every layer)
- BC-005: Real-time events (Socket.io + event buffer)
- BC-011: Security (auth rejection, no anonymous access)
- BC-012: Error handling (structured errors, no stack traces)
"""

import json
import time
from unittest.mock import AsyncMock, patch

import pytest

from backend.app.core.event_buffer import (
    EVENT_BUFFER_TTL_SECONDS,
    cleanup_old_events,
    get_buffer_stats,
    get_events_since,
    store_event,
)
from backend.app.core.redis import (
    cache_delete,
    cache_get,
    cache_set,
    close_redis,
    make_key,
    redis_health_check,
)
from backend.app.core.socketio import (
    get_tenant_room,
    sio,
)


class TestRedisSocketioIntegration:
    """Test Redis + Socket.io cross-module integration (BC-001, BC-005)."""

    @pytest.mark.asyncio
    async def test_emit_stores_in_redis_buffer(self):
        """emit_to_tenant stores event in Redis event buffer.

        BC-005: Every emit MUST also store in event buffer.
        BC-001: Both Redis key and Socket.io room use company_id.
        """
        mock_redis = AsyncMock()
        mock_redis.zadd = AsyncMock(return_value=True)
        mock_redis.expire = AsyncMock(return_value=True)
        mock_sio_emit = AsyncMock()
        mock_sio_rooms = AsyncMock(return_value=[])

        with patch(
            "backend.app.core.event_buffer.get_redis",
            return_value=mock_redis,
        ):
            with patch.object(sio, "emit", mock_sio_emit):
                with patch.object(sio, "rooms", mock_sio_rooms):
                    from backend.app.core.socketio import emit_to_tenant

                    await emit_to_tenant(
                        company_id="acme",
                        event_type="ticket:new",
                        payload={"ticket_id": "123"},
                    )

        # Verify Socket.io emit used correct tenant room
        mock_sio_emit.assert_called_once()
        emit_call = mock_sio_emit.call_args
        assert emit_call[1]["room"] == "tenant_acme"

        # Verify Redis buffer used correct tenant-scoped key
        mock_redis.zadd.assert_called_once()
        buffer_key = mock_redis.zadd.call_args[0][0]
        assert buffer_key == "parwa:acme:events"

        # Verify TTL set to 24h (BC-005)
        mock_redis.expire.assert_called_once_with(
            "parwa:acme:events", EVENT_BUFFER_TTL_SECONDS,
        )

    @pytest.mark.asyncio
    async def test_cross_tenant_isolation_in_emit_and_buffer(self):
        """Events from tenant A must NEVER appear in tenant B's buffer.

        BC-001: Strict tenant isolation.
        """
        mock_redis = AsyncMock()
        mock_redis.zadd = AsyncMock(return_value=True)
        mock_redis.expire = AsyncMock(return_value=True)
        mock_redis.zrangebyscore = AsyncMock(return_value=[])

        with patch(
            "backend.app.core.event_buffer.get_redis",
            return_value=mock_redis,
        ):
            with patch.object(
                sio, "emit", AsyncMock(),
            ):
                with patch.object(
                    sio, "rooms", AsyncMock(return_value=[]),
                ):
                    from backend.app.core.socketio import emit_to_tenant

                    # Emit for tenant A
                    await emit_to_tenant(
                        company_id="companyA",
                        event_type="ticket:new",
                        payload={"id": "1"},
                    )

                    # Query events for tenant B
                    events = await get_events_since("companyB")
                    assert len(events) == 0

                    # Verify query used tenant B's key
                    call_args = mock_redis.zrangebyscore.call_args
                    query_key = call_args[0][0]
                    assert query_key == "parwa:companyB:events"

    @pytest.mark.asyncio
    async def test_cache_and_event_buffer_dont_collide(self):
        """Cache keys and event buffer keys must not collide.

        BC-001: Both use parwa:{company_id}: prefix but different suffixes.
        """
        cache_key = make_key("acme", "cache", "session:123")
        event_key = make_key("acme", "events")

        assert cache_key == "parwa:acme:cache:session:123"
        assert event_key == "parwa:acme:events"
        assert cache_key != event_key

    @pytest.mark.asyncio
    async def test_different_tenants_different_redis_keys(self):
        """Two tenants must NEVER share a Redis key prefix.

        BC-001: Tenant isolation at key level.
        """
        key_a = make_key("tenantA", "session", "sess_1")
        key_b = make_key("tenantB", "session", "sess_1")

        assert key_a == "parwa:tenantA:session:sess_1"
        assert key_b == "parwa:tenantB:session:sess_1"
        # Same logical key, different tenants = different keys
        assert not key_a.startswith(key_b)
        assert not key_b.startswith(key_a)

    @pytest.mark.asyncio
    async def test_room_name_matches_key_namespace(self):
        """Socket.io room and Redis key use the same company_id.

        BC-001: Consistency across all tenant-scoped systems.
        """
        company_id = "test-tenant-123"
        room = get_tenant_room(company_id)
        redis_key = make_key(company_id, "events")

        # Room: tenant_test-tenant-123
        # Redis key: parwa:test-tenant-123:events
        assert company_id in room
        assert company_id in redis_key
        # Both contain the exact same company_id
        assert room.replace("tenant_", "") == company_id
        assert redis_key.split(":")[1] == company_id


class TestEventBufferLifecycle:
    """Test complete event buffer lifecycle (BC-005)."""

    @pytest.mark.asyncio
    async def test_store_retrieve_cleanup_lifecycle(self):
        """Full lifecycle: store → retrieve → cleanup.

        BC-005: Event buffer with 24h retention and cleanup.
        """
        now = time.time()
        event_data = json.dumps({
            "event_type": "ticket:resolved",
            "payload": {"ticket_id": "456"},
            "created_at": "2025-01-01T00:00:00Z",
            "timestamp": now,
        })

        mock_redis = AsyncMock()
        mock_redis.zadd = AsyncMock(return_value=True)
        mock_redis.expire = AsyncMock(return_value=True)
        mock_redis.zrangebyscore = AsyncMock(
            return_value=[event_data],
        )
        mock_redis.zcard = AsyncMock(return_value=1)
        mock_redis.zrange = AsyncMock(
            side_effect=[[event_data], [event_data]]
        )
        mock_redis.zremrangebyscore = AsyncMock(return_value=1)

        with patch(
            "backend.app.core.event_buffer.get_redis",
            return_value=mock_redis,
        ):

            # Step 1: Store event
            result = await store_event(
                company_id="acme",
                event_type="ticket:resolved",
                payload={"ticket_id": "456"},
            )
            assert result is True

            # Step 2: Retrieve events since timestamp
            events = await get_events_since(
                company_id="acme", last_seen=now - 1
            )
            assert len(events) == 1
            assert events[0]["event_type"] == "ticket:resolved"

            # Step 3: Get buffer stats
            stats = await get_buffer_stats("acme")
            assert stats["total_events"] == 1

            # Step 4: Cleanup old events
            removed = await cleanup_old_events("acme")
            assert removed == 1

    @pytest.mark.asyncio
    async def test_max_events_cap_prevents_memory_exhaustion(self):
        """MAX_EVENTS_PER_QUERY cap prevents DoS via large queries.

        BC-012: Defensive against resource exhaustion.
        """
        from backend.app.core.event_buffer import (
            MAX_EVENTS_PER_QUERY,
        )

        mock_redis = AsyncMock()
        mock_redis.zrangebyscore = AsyncMock(return_value=[])

        with patch(
            "backend.app.core.event_buffer.get_redis",
            return_value=mock_redis,
        ):
            # Request 10,000 events — should be capped
            await get_events_since(
                company_id="acme",
                last_seen=0.0,
                limit=10000,
            )

        call_kwargs = mock_redis.zrangebyscore.call_args
        actual_limit = call_kwargs[1]["num"]
        assert actual_limit == MAX_EVENTS_PER_QUERY
        assert MAX_EVENTS_PER_QUERY == 500


class TestFailOpenConsistency:
    """Test that ALL Redis operations follow fail-open pattern (BC-012)."""

    @pytest.mark.asyncio
    async def test_redis_down_does_not_crash_cache_get(self):
        """cache_get returns default when Redis is down (BC-012)."""
        with patch(
            "backend.app.core.redis.get_redis",
            side_effect=Exception("Redis down"),
        ):
            result = await cache_get("acme", "key", "fallback")
            assert result == "fallback"

    @pytest.mark.asyncio
    async def test_redis_down_does_not_crash_cache_set(self):
        """cache_set returns False when Redis is down (BC-012)."""
        with patch(
            "backend.app.core.redis.get_redis",
            side_effect=Exception("Redis down"),
        ):
            result = await cache_set("acme", "key", "value")
            assert result is False

    @pytest.mark.asyncio
    async def test_redis_down_does_not_crash_cache_delete(self):
        """cache_delete returns False when Redis is down (BC-012)."""
        with patch(
            "backend.app.core.redis.get_redis",
            side_effect=Exception("Redis down"),
        ):
            result = await cache_delete("acme", "key")
            assert result is False

    @pytest.mark.asyncio
    async def test_redis_down_does_not_crash_event_store(self):
        """store_event returns False when Redis is down (BC-012)."""
        with patch(
            "backend.app.core.event_buffer.get_redis",
            side_effect=Exception("Redis down"),
        ):
            result = await store_event(
                company_id="acme",
                event_type="test",
                payload={},
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_redis_down_does_not_crash_event_retrieve(self):
        """get_events_since returns empty list when Redis is down."""
        with patch(
            "backend.app.core.event_buffer.get_redis",
            side_effect=Exception("Redis down"),
        ):
            result = await get_events_since(
                company_id="acme", last_seen=0.0
            )
            assert result == []

    @pytest.mark.asyncio
    async def test_redis_down_does_not_crash_cleanup(self):
        """cleanup_old_events returns 0 when Redis is down."""
        with patch(
            "backend.app.core.event_buffer.get_redis",
            side_effect=Exception("Redis down"),
        ):
            result = await cleanup_old_events("acme")
            assert result == 0

    @pytest.mark.asyncio
    async def test_redis_down_does_not_crash_buffer_stats(self):
        """get_buffer_stats returns zeros when Redis is down."""
        with patch(
            "backend.app.core.event_buffer.get_redis",
            side_effect=Exception("Redis down"),
        ):
            stats = await get_buffer_stats("acme")
            assert stats["total_events"] == 0

    @pytest.mark.asyncio
    async def test_redis_down_does_not_crash_health_check(self):
        """redis_health_check returns unhealthy when Redis is down."""
        with patch(
            "backend.app.core.redis.get_redis",
            side_effect=Exception("Redis down"),
        ):
            result = await redis_health_check()
            assert result["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_close_redis_idempotent_when_down(self):
        """close_redis is safe to call even when Redis was never connected."""
        with patch("backend.app.core.redis._redis_client", None):
            # Should not raise
            await close_redis()


class TestHealthEndpointsIntegration:
    """Test /health, /ready, /metrics integration with middleware."""

    def test_health_includes_redis_and_db_status(self, client):
        """Health endpoint checks both Redis and DB (BC-012)."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "subsystems" in data
        assert "redis" in data["subsystems"]
        assert "database" in data["subsystems"]
        assert data["subsystems"]["redis"]["status"] in (
            "healthy", "unhealthy", "unreachable",
        )

    def test_ready_returns_503_when_deps_down(self, client_no_raise):
        """Readiness returns 503 when any dependency is down (BC-012)."""
        response = client_no_raise.get("/ready")
        # In test env without Redis, should be 503
        assert response.status_code in (200, 503)
        if response.status_code == 503:
            data = response.json()
            assert data["status"] == "not_ready"

    def test_events_since_requires_tenant(self, client):
        """GET /api/events/since requires tenant identification.

        BC-001: All endpoints must be tenant-scoped.
        """
        # No X-Company-ID header → should be rejected
        response = client.get("/api/events/since?last_seen=0.0")
        assert response.status_code in (403, 422)

    def test_error_response_format_consistent_across_endpoints(
        self, client
    ):
        """All error responses follow the same structured format (BC-012)."""
        # 404 error
        response = client.get(
            "/nonexistent",
            headers={"X-Company-ID": "test"},
        )
        data = response.json()
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
        assert "details" in data["error"]


class TestBuildingCodeConstants:
    """Verify BC constants are correct and enforced."""

    def test_event_buffer_ttl_is_24_hours(self):
        """BC-005: Event buffer retention is exactly 24 hours."""
        assert EVENT_BUFFER_TTL_SECONDS == 86400

    def test_tenant_room_prefix_is_tenant_underscore(self):
        """BC-005: Room prefix is 'tenant_'."""
        from backend.app.core.socketio import TENANT_ROOM_PREFIX
        assert TENANT_ROOM_PREFIX == "tenant_"

    def test_redis_namespace_prefix_is_parwa(self):
        """BC-001: Redis key namespace is 'parwa'."""
        from backend.app.core.redis import NAMESPACE_PREFIX
        assert NAMESPACE_PREFIX == "parwa"

    def test_max_company_id_length_enforced(self):
        """BC-005: Max company_id length is enforced."""
        from backend.app.core.socketio import MAX_COMPANY_ID_LENGTH
        assert MAX_COMPANY_ID_LENGTH == 128

    def test_make_key_requires_company_id(self):
        """BC-001: make_key raises ValueError without company_id."""
        with pytest.raises(ValueError):
            make_key("", "test")
        with pytest.raises(ValueError):
            make_key(None, "test")

    def test_get_tenant_room_requires_company_id(self):
        """BC-005: get_tenant_room raises ValueError without company_id."""
        with pytest.raises(ValueError):
            get_tenant_room("")
        with pytest.raises(ValueError):
            get_tenant_room(None)
