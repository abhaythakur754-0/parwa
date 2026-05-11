"""
Tests for PARWA Redis Connection Layer (Day 5)

Tests:
- Key namespace format: parwa:{company_id}:* (BC-001)
- make_key validation (empty, whitespace, control chars)
- cache_get/cache_set/cache_delete (with mocked Redis)
- redis_health_check (fail-open on Redis down)
- close_redis idempotent
"""

from unittest.mock import AsyncMock, patch

import pytest

from backend.app.core.redis import (
    cache_delete,
    cache_get,
    cache_set,
    close_redis,
    make_key,
    redis_health_check,
)


class TestMakeKey:
    """Test tenant-scoped key generation (BC-001)."""

    def test_basic_key_format(self):
        """Key follows parwa:{company_id}:{part} format."""
        result = make_key("acme", "session", "sess_123")
        assert result == "parwa:acme:session:sess_123"

    def test_single_part(self):
        """Key with one additional part works."""
        result = make_key("acme", "rate_limit")
        assert result == "parwa:acme:rate_limit"

    def test_multiple_parts(self):
        """Key with multiple additional parts works."""
        result = make_key("acme", "cache", "user", "settings")
        assert result == "parwa:acme:cache:user:settings"

    def test_company_id_stripped(self):
        """Whitespace around company_id is stripped."""
        result = make_key("  acme  ", "test")
        assert result == "parwa:acme:test"

    def test_empty_company_id_raises(self):
        """Empty company_id raises ValueError (BC-001)."""
        with pytest.raises(ValueError, match="company_id is required"):
            make_key("", "test")

    def test_none_company_id_raises(self):
        """None company_id raises ValueError (BC-001)."""
        with pytest.raises(ValueError, match="company_id is required"):
            make_key(None, "test")

    def test_int_company_id_raises(self):
        """Non-string company_id raises ValueError (BC-001)."""
        with pytest.raises(ValueError, match="company_id is required"):
            make_key(123, "test")

    def test_whitespace_only_company_id_raises(self):
        """Whitespace-only company_id raises ValueError (BC-001)."""
        with pytest.raises(ValueError, match="whitespace-only"):
            make_key("   ", "test")

    def test_control_chars_raises(self):
        """Control characters in company_id raises ValueError."""
        with pytest.raises(ValueError, match="control characters"):
            make_key("acme\x00evil", "test")

    def test_newline_raises(self):
        """Newline in company_id raises ValueError."""
        with pytest.raises(ValueError, match="control characters"):
            make_key("acme\ntest", "key")

    def test_normal_characters_work(self):
        """Normal characters (alphanumeric, hyphen, underscore) work."""
        result = make_key("company-123_test", "data")
        assert result == "parwa:company-123_test:data"

    def test_namespace_prefix_is_parwa(self):
        """All keys start with 'parwa:' prefix (BC-001)."""
        result = make_key("x", "y")
        assert result.startswith("parwa:")

    def test_company_id_is_second_segment(self):
        """company_id is always the second segment (BC-001)."""
        result = make_key("mytenant", "a", "b", "c")
        parts = result.split(":")
        assert parts[0] == "parwa"
        assert parts[1] == "mytenant"


class TestCacheOperations:
    """Test cache_get/cache_set/cache_delete with mocked Redis."""

    @pytest.mark.asyncio
    async def test_cache_set_success(self):
        """cache_set calls Redis SET with TTL."""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        with patch(
            "backend.app.core.redis.get_redis",
            return_value=mock_redis,
        ):
            result = await cache_set(
                "acme", "user:123", {"name": "John"}
            )
            assert result is True
            mock_redis.set.assert_called_once()
            # Verify the key is namespaced
            call_args = mock_redis.set.call_args
            key = call_args[0][0]
            assert key.startswith("parwa:acme:cache:")

    @pytest.mark.asyncio
    async def test_cache_set_with_custom_ttl(self):
        """cache_set uses custom TTL."""
        mock_redis = AsyncMock()
        with patch(
            "backend.app.core.redis.get_redis",
            return_value=mock_redis,
        ):
            await cache_set(
                "acme", "key", "val", ttl_seconds=600
            )
            call_kwargs = mock_redis.set.call_args
            assert call_kwargs[1]["ex"] == 600

    @pytest.mark.asyncio
    async def test_cache_get_miss(self):
        """cache_get returns default on cache miss."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        with patch(
            "backend.app.core.redis.get_redis",
            return_value=mock_redis,
        ):
            result = await cache_get(
                "acme", "missing", "default_val"
            )
            assert result == "default_val"

    @pytest.mark.asyncio
    async def test_cache_get_hit_json(self):
        """cache_get deserializes JSON values."""
        import json
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps({"id": 1}))
        with patch(
            "backend.app.core.redis.get_redis",
            return_value=mock_redis,
        ):
            result = await cache_get("acme", "user:1")
            assert result == {"id": 1}

    @pytest.mark.asyncio
    async def test_cache_get_hit_string(self):
        """cache_get returns plain strings as-is."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="plain_string")
        with patch(
            "backend.app.core.redis.get_redis",
            return_value=mock_redis,
        ):
            result = await cache_get("acme", "simple")
            assert result == "plain_string"

    @pytest.mark.asyncio
    async def test_cache_delete_success(self):
        """cache_delete calls Redis DEL."""
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(return_value=True)
        with patch(
            "backend.app.core.redis.get_redis",
            return_value=mock_redis,
        ):
            result = await cache_delete("acme", "key")
            assert result is True
            mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_operations_fail_open(self):
        """cache operations return default/False on Redis error (BC-012)."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=Exception("Redis down"))
        mock_redis.set = AsyncMock(side_effect=Exception("Redis down"))
        mock_redis.delete = AsyncMock(
            side_effect=Exception("Redis down")
        )
        with patch(
            "backend.app.core.redis.get_redis",
            return_value=mock_redis,
        ):
            assert await cache_get(
                "acme", "x", "fallback"
            ) == "fallback"
            assert await cache_set("acme", "x", "val") is False
            assert await cache_delete("acme", "x") is False


class TestRedisHealthCheck:
    """Test Redis health check (BC-012)."""

    @pytest.mark.asyncio
    async def test_healthy_redis(self):
        """Health check returns healthy when Redis responds to PING."""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        with patch(
            "backend.app.core.redis.get_redis",
            return_value=mock_redis,
        ):
            result = await redis_health_check()
            assert result["status"] == "healthy"
            assert "latency_ms" in result
            assert result["latency_ms"] >= 0

    @pytest.mark.asyncio
    async def test_unhealthy_redis(self):
        """Health check returns unhealthy when Redis fails."""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(
            side_effect=Exception("Connection refused")
        )
        with patch(
            "backend.app.core.redis.get_redis",
            return_value=mock_redis,
        ):
            result = await redis_health_check()
            assert result["status"] == "unhealthy"
            assert "error" in result

    @pytest.mark.asyncio
    async def test_health_check_fail_open(self):
        """Health check doesn't raise even when get_redis fails."""
        with patch(
            "backend.app.core.redis.get_redis",
            side_effect=Exception("No Redis config"),
        ):
            result = await redis_health_check()
            assert result["status"] == "unhealthy"


class TestCloseRedis:
    """Test Redis connection cleanup."""

    @pytest.mark.asyncio
    async def test_close_idempotent(self):
        """close_redis can be called multiple times without error."""
        # First call — _redis_client is None
        await close_redis()
        # Second call — still None, should not raise
        await close_redis()

    @pytest.mark.asyncio
    async def test_close_clears_client(self):
        """close_redis sets the client to None after closing."""
        mock_redis = AsyncMock()
        mock_redis.aclose = AsyncMock(return_value=True)
        import backend.app.core.redis as redis_mod
        redis_mod._redis_client = mock_redis
        await close_redis()
        assert redis_mod._redis_client is None
