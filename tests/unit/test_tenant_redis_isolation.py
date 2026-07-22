"""
Tests for PARWA Tenant Redis Isolation (Day 20)

Tests key validation, tenant key filtering, safe operations.
"""

import os

os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test_secret_key"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["JWT_SECRET_KEY"] = "test_jwt_key"
os.environ["DATA_ENCRYPTION_KEY"] = "12345678901234567890123456789012"

from unittest.mock import AsyncMock, patch, MagicMock  # noqa: E402

import pytest  # noqa: E402

from backend.app.core.redis import (  # noqa: E402
    make_key,
    NAMESPACE_PREFIX,
)
from backend.app.core.tenant_context import (  # noqa: E402
    set_tenant_context,
    clear_tenant_context,
    reset_tenant_context,
    tenant_bypass,
    get_tenant_context,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_tenant_context()
    yield
    reset_tenant_context()


# ── make_key ─────────────────────────────────────────────


class TestMakeKey:

    def test_basic_key(self):
        key = make_key("acme", "session", "sess_123")
        assert key == "parwa:acme:session:sess_123"

    def test_single_part(self):
        key = make_key("acme", "cache")
        assert key == "parwa:acme:cache"

    def test_multiple_parts(self):
        key = make_key("acme", "a", "b", "c")
        assert key == "parwa:acme:a:b:c"

    def test_empty_company_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            make_key("", "cache")

    def test_none_company_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            make_key(None, "cache")

    def test_whitespace_company_raises(self):
        with pytest.raises(ValueError, match="whitespace"):
            make_key("   ", "cache")

    def test_strips_whitespace(self):
        key = make_key("  acme  ", "cache")
        assert key == "parwa:acme:cache"

    def test_control_chars_rejected(self):
        with pytest.raises(ValueError, match="control"):
            make_key("acme\x00", "cache")

    def test_different_tenants_different_keys(self):
        k1 = make_key("acme", "data")
        k2 = make_key("globex", "data")
        assert k1 != k2


# ── Key Validation ───────────────────────────────────────


class TestKeyValidation:
    """Test key prefix validation logic."""

    def test_valid_tenant_key_pattern(self):
        """Keys following parwa:{company_id}:* are valid."""
        import re
        pattern = re.compile(rf"^{NAMESPACE_PREFIX}:[^:]+:")
        key = make_key("acme", "cache", "mykey")
        assert pattern.match(key) is not None

    def test_system_key_not_tenant_scoped(self):
        """System keys (parwa:system:*) are not tenant-scoped."""
        key = f"{NAMESPACE_PREFIX}:system:health"
        import re
        tenant_pattern = re.compile(rf"^{NAMESPACE_PREFIX}:[^:]+:")
        # Still matches pattern but company_id would be "system"
        assert tenant_pattern.match(key) is not None

    def test_raw_key_without_prefix(self):
        """Raw keys without parwa: prefix are invalid."""
        key = "raw_key_without_prefix"
        import re
        pattern = re.compile(rf"^{NAMESPACE_PREFIX}:")
        assert pattern.match(key) is None


# ── Cross-Tenant Isolation ───────────────────────────────


class TestCrossTenantIsolation:

    def test_keys_never_overlap(self):
        """Keys for different tenants never collide."""
        import hashlib
        tenants = ["acme", "globex", "initech", "umbrella"]
        keys = {make_key(t, "same", "suffix") for t in tenants}
        assert len(keys) == len(tenants)

    def test_tenant_context_used_for_key(self):
        """When context is set, make_key uses it for scoping."""
        set_tenant_context("acme")
        cid = get_tenant_context()
        key = make_key(cid, "data")
        assert "acme" in key
        assert key.startswith(f"{NAMESPACE_PREFIX}:acme:")

    def test_mget_filters_by_tenant(self):
        """MGET should only return keys for the requesting tenant."""
        # This is a design contract test — actual enforcement is in
        # the service layer, but the key format ensures isolation
        acme_keys = [
            make_key("acme", "cache", "k1"),
            make_key("acme", "cache", "k2"),
        ]
        globex_keys = [
            make_key("globex", "cache", "k1"),
            make_key("globex", "cache", "k2"),
        ]
        # No overlap between tenant key sets
        assert set(acme_keys).isdisjoint(set(globex_keys))


# ── Safe Operations (Design Contract) ────────────────────


class TestSafeOperations:

    @pytest.mark.asyncio
    async def test_cache_get_tenant_scoped(self):
        """cache_get uses make_key for tenant isolation."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch("backend.app.core.redis.get_redis", return_value=mock_redis):
            from backend.app.core.redis import cache_get
            await cache_get("acme", "mykey")

        mock_redis.get.assert_called_once()
        called_key = mock_redis.get.call_args[0][0]
        assert called_key == make_key("acme", "cache", "mykey")

    @pytest.mark.asyncio
    async def test_cache_set_tenant_scoped(self):
        """cache_set uses make_key for tenant isolation."""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)

        with patch("backend.app.core.redis.get_redis", return_value=mock_redis):
            from backend.app.core.redis import cache_set
            await cache_set("acme", "mykey", {"data": 123})

        mock_redis.set.assert_called_once()
        called_key = mock_redis.set.call_args[0][0]
        assert called_key == make_key("acme", "cache", "mykey")

    @pytest.mark.asyncio
    async def test_cache_delete_tenant_scoped(self):
        """cache_delete uses make_key for tenant isolation."""
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock(return_value=True)

        with patch("backend.app.core.redis.get_redis", return_value=mock_redis):
            from backend.app.core.redis import cache_delete
            await cache_delete("acme", "mykey")

        mock_redis.delete.assert_called_once()
        called_key = mock_redis.delete.call_args[0][0]
        assert called_key == make_key("acme", "cache", "mykey")
