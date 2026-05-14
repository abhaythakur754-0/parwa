"""
Tests for Redis Key Namespace Manager (Phase 6: Production Hardening)

Tests cover:
- build_key: standard pattern, suffix, validation
- get_ttl: default and custom override
- validate_key: valid and invalid characters
- cleanup_namespace: async Redis operations
- get_namespace_metrics: async metrics gathering
- audit_all_keys: finding orphans
- fix_missing_ttls: dry run and live modes
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.redis_key_manager import (
    NAMESPACE_PREFIX,
    NAMESPACE_TTL_DEFAULTS,
    RedisNamespace,
    audit_all_keys,
    build_key,
    cleanup_namespace,
    fix_missing_ttls,
    get_namespace_metrics,
    get_ttl,
    identify_namespace,
    parse_key,
    startup_audit,
    validate_key,
)


# ═══════════════════════════════════════════════════════════════════════
# build_key tests
# ═══════════════════════════════════════════════════════════════════════


class TestBuildKey:
    """Tests for build_key() function."""

    def test_build_key_standard_pattern(self):
        """build_key produces parwa:{namespace}:{company_id}:{key}."""
        key = build_key(RedisNamespace.CACHE, "BC-001", "query:hello")
        assert key == "parwa:cache:BC-001:query:hello"

    def test_build_key_with_suffix(self):
        """build_key with suffix appends additional segment."""
        key = build_key(
            RedisNamespace.JARVIS_BRIDGE,
            "acme",
            "session_123",
            suffix="state",
        )
        assert key == "parwa:jarvis:bridge:acme:session_123:state"

    def test_build_key_different_namespaces(self):
        """build_key works with all namespace values."""
        for ns in RedisNamespace:
            key = build_key(ns, "test_co", "mykey")
            assert key.startswith(f"parwa:{ns.value}:test_co:mykey")

    def test_build_key_validates_company_id_empty(self):
        """build_key raises ValueError for empty company_id."""
        with pytest.raises(ValueError, match="company_id"):
            build_key(RedisNamespace.CACHE, "", "key")

    def test_build_key_validates_company_id_whitespace(self):
        """build_key raises ValueError for whitespace-only company_id."""
        with pytest.raises(ValueError, match="whitespace"):
            build_key(RedisNamespace.CACHE, "   ", "key")

    def test_build_key_validates_company_id_control_chars(self):
        """build_key raises ValueError for control characters in company_id."""
        with pytest.raises(ValueError, match="control characters"):
            build_key(RedisNamespace.CACHE, "co\nid", "key")

    def test_build_key_validates_company_id_none(self):
        """build_key raises ValueError for None company_id."""
        with pytest.raises(ValueError, match="company_id"):
            build_key(RedisNamespace.CACHE, None, "key")  # type: ignore

    def test_build_key_validates_key_empty(self):
        """build_key raises ValueError for empty key."""
        with pytest.raises(ValueError, match="key"):
            build_key(RedisNamespace.CACHE, "co1", "")

    def test_build_key_validates_key_whitespace(self):
        """build_key raises ValueError for whitespace-only key."""
        with pytest.raises(ValueError, match="whitespace"):
            build_key(RedisNamespace.CACHE, "co1", "   ")

    def test_build_key_validates_suffix_empty(self):
        """build_key raises ValueError for empty suffix."""
        with pytest.raises(ValueError, match="suffix"):
            build_key(RedisNamespace.CACHE, "co1", "key", suffix="")

    def test_build_key_strips_whitespace_company_id(self):
        """build_key strips whitespace from company_id."""
        key = build_key(RedisNamespace.CACHE, "  acme  ", "key")
        assert key == "parwa:cache:acme:key"

    def test_build_key_colon_namespace(self):
        """build_key handles namespaces with colons (e.g., jarvis:bridge)."""
        key = build_key(RedisNamespace.JARVIS_BRIDGE, "co1", "sess1")
        assert key == "parwa:jarvis:bridge:co1:sess1"

    def test_build_key_no_suffix(self):
        """build_key without suffix doesn't add trailing colon."""
        key = build_key(RedisNamespace.SESSION, "co1", "sess_123")
        assert key == "parwa:session:co1:sess_123"
        assert not key.endswith(":")


# ═══════════════════════════════════════════════════════════════════════
# get_ttl tests
# ═══════════════════════════════════════════════════════════════════════


class TestGetTTL:
    """Tests for get_ttl() function."""

    def test_get_ttl_default(self):
        """get_ttl returns default TTL for namespace."""
        ttl = get_ttl(RedisNamespace.CACHE)
        assert ttl == 120  # 2 minutes

    def test_get_ttl_default_session(self):
        """get_ttl returns 24h TTL for SESSION namespace."""
        ttl = get_ttl(RedisNamespace.SESSION)
        assert ttl == 86400

    def test_get_ttl_custom_override(self):
        """get_ttl with custom_ttl returns the override value."""
        ttl = get_ttl(RedisNamespace.CACHE, custom_ttl=600)
        assert ttl == 600

    def test_get_ttl_custom_override_zero(self):
        """get_ttl with custom_ttl=0 falls back to default."""
        ttl = get_ttl(RedisNamespace.CACHE, custom_ttl=0)
        assert ttl == 120  # Falls back to default since 0 is not > 0

    def test_get_ttl_custom_override_negative(self):
        """get_ttl with negative custom_ttl falls back to default."""
        ttl = get_ttl(RedisNamespace.CACHE, custom_ttl=-1)
        assert ttl == 120  # Falls back to default since -1 is not > 0

    def test_get_ttl_all_namespaces_have_defaults(self):
        """Every RedisNamespace has a TTL default."""
        for ns in RedisNamespace:
            ttl = get_ttl(ns)
            assert ttl > 0, f"Namespace {ns.value} has no TTL default"

    def test_get_ttl_lock_namespace(self):
        """LOCK namespace has very short TTL (30 seconds)."""
        ttl = get_ttl(RedisNamespace.LOCK)
        assert ttl == 30

    def test_get_ttl_guardrails_namespace(self):
        """GUARDRAILS namespace has very long TTL (90 days)."""
        ttl = get_ttl(RedisNamespace.GUARDRAILS)
        assert ttl == 90 * 24 * 60 * 60


# ═══════════════════════════════════════════════════════════════════════
# validate_key tests
# ═══════════════════════════════════════════════════════════════════════


class TestValidateKey:
    """Tests for validate_key() function."""

    def test_validate_key_valid_characters(self):
        """validate_key returns True for alphanumeric, hyphens, underscores, colons."""
        assert validate_key("parwa:cache:co1:key1") is True
        assert validate_key("simple_key-123") is True
        assert validate_key("a:b:c:d") is True
        assert validate_key("key.with.period") is True

    def test_validate_key_invalid_characters(self):
        """validate_key returns False for spaces, special chars, control chars."""
        assert validate_key("key with space") is False
        assert validate_key("key\twith\ttab") is False
        assert validate_key("key\nnewline") is False
        assert validate_key("key@symbol") is False
        assert validate_key("key#hash") is False
        assert validate_key("") is False
        assert validate_key(None) is False  # type: ignore

    def test_validate_key_empty_string(self):
        """validate_key returns False for empty string."""
        assert validate_key("") is False

    def test_validate_key_single_char(self):
        """validate_key returns True for single alphanumeric char."""
        assert validate_key("a") is True
        assert validate_key("1") is True

    def test_validate_key_long_key(self):
        """validate_key handles long keys."""
        long_key = "parwa:cache:co1:" + "a" * 500
        assert validate_key(long_key) is True


# ═══════════════════════════════════════════════════════════════════════
# parse_key tests
# ═══════════════════════════════════════════════════════════════════════


class TestParseKey:
    """Tests for parse_key() function."""

    def test_parse_key_standard(self):
        """parse_key correctly parses a standard build_key output."""
        key = build_key(RedisNamespace.CACHE, "co1", "mykey")
        result = parse_key(key)
        assert result is not None
        assert result["prefix"] == "parwa"
        assert result["namespace"] == "cache"
        assert result["company_id"] == "co1"
        assert result["key"] == "mykey"

    def test_parse_key_with_suffix(self):
        """parse_key correctly handles keys with suffixes."""
        key = build_key(RedisNamespace.CACHE, "co1", "mykey", suffix="extra")
        result = parse_key(key)
        assert result is not None
        assert result["suffix"] == "extra"

    def test_parse_key_colon_namespace(self):
        """parse_key handles namespaces with colons."""
        key = build_key(RedisNamespace.JARVIS_BRIDGE, "co1", "sess1")
        result = parse_key(key)
        assert result is not None
        assert result["namespace"] == "jarvis:bridge"
        assert result["company_id"] == "co1"

    def test_parse_key_invalid(self):
        """parse_key returns None for invalid keys."""
        assert parse_key("") is None
        assert parse_key("invalid") is None
        assert parse_key("parma:co1:key") is None  # Wrong prefix
        assert parse_key(None) is None  # type: ignore


# ═══════════════════════════════════════════════════════════════════════
# identify_namespace tests
# ═══════════════════════════════════════════════════════════════════════


class TestIdentifyNamespace:
    """Tests for identify_namespace() function."""

    def test_identify_cache_namespace(self):
        """identify_namespace identifies cache keys."""
        assert identify_namespace("parwa:co1:cache:query") == RedisNamespace.CACHE

    def test_identify_health_namespace(self):
        """identify_namespace identifies health keys."""
        assert identify_namespace("health:google:gemma") == RedisNamespace.HEALTH

    def test_identify_jarvis_bridge_namespace(self):
        """identify_namespace identifies jarvis bridge keys."""
        assert identify_namespace("parwa:co1:jarvis:bridge:sess1") == RedisNamespace.JARVIS_BRIDGE

    def test_identify_unknown_key(self):
        """identify_namespace returns None for unknown patterns."""
        assert identify_namespace("random_key_12345") is None
        assert identify_namespace("") is None

    def test_identify_rate_limit_namespace(self):
        """identify_namespace identifies rate limit keys."""
        assert identify_namespace("parwa:rl:abc123") == RedisNamespace.RATE_LIMIT

    def test_identify_migration_namespace(self):
        """identify_namespace identifies migration keys."""
        assert identify_namespace("migration:co1:circuit") == RedisNamespace.MIGRATION


# ═══════════════════════════════════════════════════════════════════════
# Async operation tests (with mocked Redis)
# ═══════════════════════════════════════════════════════════════════════


class TestCleanupNamespace:
    """Tests for cleanup_namespace() function."""

    @pytest.mark.asyncio
    async def test_cleanup_namespace(self):
        """cleanup_namespace deletes keys matching namespace pattern."""
        mock_redis = AsyncMock()
        # Mock scan_iter returning async generator
        async def mock_scan(*args, **kwargs):
            for key in ["parwa:cache:co1:key1", "parwa:cache:co1:key2"]:
                yield key

        mock_redis.scan_iter = mock_scan
        mock_redis.delete = AsyncMock(return_value=2)

        deleted = await cleanup_namespace(mock_redis, RedisNamespace.CACHE, "co1")
        assert deleted == 2
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_namespace_no_keys(self):
        """cleanup_namespace returns 0 when no keys match."""
        mock_redis = AsyncMock()

        async def mock_scan(*args, **kwargs):
            return
            yield  # Make it an async generator

        mock_redis.scan_iter = mock_scan

        deleted = await cleanup_namespace(mock_redis, RedisNamespace.CACHE, "co1")
        assert deleted == 0

    @pytest.mark.asyncio
    async def test_cleanup_namespace_error(self):
        """cleanup_namespace returns 0 on error (BC-008)."""
        mock_redis = AsyncMock()
        mock_redis.scan_iter = MagicMock(side_effect=Exception("Redis down"))

        deleted = await cleanup_namespace(mock_redis, RedisNamespace.CACHE, "co1")
        assert deleted == 0


class TestGetNamespaceMetrics:
    """Tests for get_namespace_metrics() function."""

    @pytest.mark.asyncio
    async def test_get_namespace_metrics(self):
        """get_namespace_metrics returns key count and TTL distribution."""
        mock_redis = AsyncMock()

        async def mock_scan(*args, **kwargs):
            for key in ["parwa:cache:co1:key1", "parwa:cache:co1:key2"]:
                yield key

        mock_redis.scan_iter = mock_scan
        mock_redis.ttl = AsyncMock(return_value=60)
        mock_redis.memory_usage = AsyncMock(return_value=128)

        metrics = await get_namespace_metrics(mock_redis, RedisNamespace.CACHE, "co1")

        assert metrics["key_count"] == 2
        assert metrics["namespace"] == "cache"
        assert "ttl_distribution" in metrics

    @pytest.mark.asyncio
    async def test_get_namespace_metrics_empty(self):
        """get_namespace_metrics returns zeros when no keys found."""
        mock_redis = AsyncMock()

        async def mock_scan(*args, **kwargs):
            return
            yield

        mock_redis.scan_iter = mock_scan

        metrics = await get_namespace_metrics(mock_redis, RedisNamespace.CACHE, "co1")
        assert metrics["key_count"] == 0
        assert metrics["memory_estimate_bytes"] == 0

    @pytest.mark.asyncio
    async def test_get_namespace_metrics_error(self):
        """get_namespace_metrics returns error info on failure (BC-008)."""
        mock_redis = AsyncMock()
        mock_redis.scan_iter = MagicMock(side_effect=Exception("Redis error"))

        metrics = await get_namespace_metrics(mock_redis, RedisNamespace.CACHE, "co1")
        assert metrics["key_count"] == 0
        assert "error" in metrics


class TestAuditAllKeys:
    """Tests for audit_all_keys() function."""

    @pytest.mark.asyncio
    async def test_audit_all_keys_finds_orphans(self):
        """audit_all_keys identifies orphaned keys."""
        mock_redis = AsyncMock()
        mock_redis.dbsize = AsyncMock(return_value=5)

        async def mock_scan(*args, **kwargs):
            for key in [
                "parwa:co1:cache:key1",       # Standard (old pattern)
                "health:google:gemma",          # Orphan (no parwa prefix)
                "parwa:co1:events",             # Standard (old pattern)
                "brand_voice:co1",              # Orphan (no parwa prefix)
                "unknown_random_key",           # Orphan
            ]:
                yield key

        mock_redis.scan_iter = mock_scan
        mock_redis.ttl = AsyncMock(return_value=60)
        mock_redis.memory_usage = AsyncMock(return_value=64)

        result = await audit_all_keys(mock_redis)

        assert result["total_key_count"] == 5
        assert result["scanned_key_count"] == 5
        assert result["orphaned_key_count"] == 3  # health, brand_voice, unknown
        assert "health:google:gemma" in result["orphaned_keys"]
        assert "brand_voice:co1" in result["orphaned_keys"]
        assert "unknown_random_key" in result["orphaned_keys"]
        assert "audit_timestamp" in result

    @pytest.mark.asyncio
    async def test_audit_all_keys_error(self):
        """audit_all_keys handles errors gracefully (BC-008)."""
        mock_redis = AsyncMock()
        mock_redis.dbsize = AsyncMock(side_effect=Exception("Connection refused"))

        result = await audit_all_keys(mock_redis)
        assert result["total_key_count"] == 0
        assert "error" in result


class TestFixMissingTtls:
    """Tests for fix_missing_ttls() function."""

    @pytest.mark.asyncio
    async def test_fix_missing_ttls_dry_run(self):
        """fix_missing_ttls in dry_run mode reports but doesn't modify."""
        mock_redis = AsyncMock()

        async def mock_scan(*args, **kwargs):
            for key in ["parwa:co1:cache:key1", "parwa:co1:session:s1"]:
                yield key

        mock_redis.scan_iter = mock_scan
        # First key has no TTL (-1), second has TTL (60)
        mock_redis.ttl = AsyncMock(side_effect=[-1, 60])
        mock_redis.expire = AsyncMock(return_value=True)

        result = await fix_missing_ttls(mock_redis, dry_run=True)

        assert result["dry_run"] is True
        assert result["keys_fixed"] == 1
        # expire should NOT have been called in dry_run
        mock_redis.expire.assert_not_called()

    @pytest.mark.asyncio
    async def test_fix_missing_ttls_live(self):
        """fix_missing_ttls in live mode actually applies TTLs."""
        mock_redis = AsyncMock()

        async def mock_scan(*args, **kwargs):
            for key in ["parwa:co1:cache:key1"]:
                yield key

        mock_redis.scan_iter = mock_scan
        mock_redis.ttl = AsyncMock(return_value=-1)  # No TTL
        mock_redis.expire = AsyncMock(return_value=True)

        result = await fix_missing_ttls(mock_redis, dry_run=False)

        assert result["dry_run"] is False
        assert result["keys_fixed"] == 1
        # expire SHOULD have been called in live mode
        mock_redis.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_fix_missing_ttls_no_missing(self):
        """fix_missing_ttls returns 0 when all keys have TTLs."""
        mock_redis = AsyncMock()

        async def mock_scan(*args, **kwargs):
            for key in ["parwa:co1:cache:key1"]:
                yield key

        mock_redis.scan_iter = mock_scan
        mock_redis.ttl = AsyncMock(return_value=300)  # Has TTL

        result = await fix_missing_ttls(mock_redis, dry_run=True)
        assert result["keys_fixed"] == 0


class TestStartupAudit:
    """Tests for startup_audit() function."""

    @pytest.mark.asyncio
    async def test_startup_audit_runs(self):
        """startup_audit completes without error."""
        mock_redis = AsyncMock()
        mock_redis.dbsize = AsyncMock(return_value=0)

        async def mock_scan(*args, **kwargs):
            return
            yield

        mock_redis.scan_iter = mock_scan

        # Should not raise
        await startup_audit(mock_redis)

    @pytest.mark.asyncio
    async def test_startup_audit_error(self):
        """startup_audit handles errors without crashing (BC-008)."""
        mock_redis = AsyncMock()
        mock_redis.dbsize = AsyncMock(side_effect=Exception("Redis down"))

        # Should not raise
        await startup_audit(mock_redis)


# ═══════════════════════════════════════════════════════════════════════
# Integration: namespaced cache operations via redis.py
# ═══════════════════════════════════════════════════════════════════════


class TestNamespacedCacheOperations:
    """Tests for namespaced_set/get/delete in redis.py."""

    @pytest.mark.asyncio
    async def test_namespaced_set_and_get(self):
        """namespaced_set and namespaced_get work with auto-TTL."""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.get = AsyncMock(return_value='{"data": 1}')
        mock_redis.delete = AsyncMock(return_value=1)

        with patch("app.core.redis.get_redis", return_value=mock_redis):
            from app.core.redis import namespaced_set, namespaced_get, namespaced_delete

            # Set
            result = await namespaced_set(
                RedisNamespace.CACHE, "co1", "test_key", {"data": 1}
            )
            assert result is True

            # Verify set was called with correct key and TTL
            call_args = mock_redis.set.call_args
            assert call_args[0][0] == "parwa:cache:co1:test_key"
            assert call_args[1]["ex"] == 120  # CACHE default TTL

            # Get
            value = await namespaced_get(RedisNamespace.CACHE, "co1", "test_key")
            assert value == {"data": 1}

            # Delete
            deleted = await namespaced_delete(RedisNamespace.CACHE, "co1", "test_key")
            assert deleted is True

    @pytest.mark.asyncio
    async def test_namespaced_set_with_ttl_override(self):
        """namespaced_set respects ttl_override parameter."""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)

        with patch("app.core.redis.get_redis", return_value=mock_redis):
            from app.core.redis import namespaced_set

            result = await namespaced_set(
                RedisNamespace.CACHE, "co1", "key", "value",
                ttl_override=600,
            )
            assert result is True

            call_args = mock_redis.set.call_args
            assert call_args[1]["ex"] == 600  # Override TTL

    @pytest.mark.asyncio
    async def test_namespaced_get_missing_key(self):
        """namespaced_get returns default for missing keys."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch("app.core.redis.get_redis", return_value=mock_redis):
            from app.core.redis import namespaced_get

            value = await namespaced_get(
                RedisNamespace.CACHE, "co1", "missing",
                default="not_found",
            )
            assert value == "not_found"


# ═══════════════════════════════════════════════════════════════════════
# Backward compatibility: make_key still works
# ═══════════════════════════════════════════════════════════════════════


class TestBackwardCompatibility:
    """Ensure existing make_key() still works alongside build_key()."""

    def test_make_key_still_works(self):
        """make_key from redis.py still produces valid keys."""
        from app.core.redis import make_key

        key = make_key("co1", "cache", "mykey")
        assert key == "parwa:co1:cache:mykey"

    def test_build_key_different_pattern(self):
        """build_key uses new pattern (namespace before company_id)."""
        key_old = "parwa:co1:cache:mykey"  # make_key pattern
        key_new = build_key(RedisNamespace.CACHE, "co1", "mykey")  # build_key pattern
        assert key_new == "parwa:cache:co1:mykey"  # Different order

    def test_validate_tenant_key_works_with_both(self):
        """validate_tenant_key accepts both old and new patterns."""
        from app.core.redis import validate_tenant_key

        old_key = "parwa:co1:cache:mykey"
        new_key = "parwa:cache:co1:mykey"

        assert validate_tenant_key(old_key) is True
        assert validate_tenant_key(new_key) is True
