"""Tests for Rate Limiting and API Key Management"""
import pytest
import time
from enterprise.api_gateway.rate_limiter import (
    RateLimiter, RateLimitStrategy, RateLimitConfig, RateLimitResult
)
from enterprise.api_gateway.api_key_manager import (
    APIKeyManager, APIKeyStatus, APIKey
)


class TestRateLimiter:
    """Tests for RateLimiter"""

    @pytest.fixture
    def limiter(self):
        return RateLimiter(strategy=RateLimitStrategy.TOKEN_BUCKET)

    def test_allows_request(self, limiter):
        config = RateLimitConfig(requests_per_second=10, burst_size=20)
        result = limiter.check_rate_limit("test_key", config)
        assert result.allowed is True

    def test_rate_limits_when_exhausted(self, limiter):
        config = RateLimitConfig(requests_per_second=1, burst_size=2)
        for _ in range(3):
            limiter.check_rate_limit("test_key", config)
        result = limiter.check_rate_limit("test_key", config)
        assert result.allowed is False

    def test_get_metrics(self, limiter):
        config = RateLimitConfig()
        limiter.check_rate_limit("key1", config)
        metrics = limiter.get_metrics()
        assert metrics["total_requests"] == 1

    def test_sliding_window_strategy(self):
        limiter = RateLimiter(strategy=RateLimitStrategy.SLIDING_WINDOW)
        config = RateLimitConfig(requests_per_second=5, window_size_seconds=1)
        result = limiter.check_rate_limit("test", config)
        assert result.allowed is True

    def test_fixed_window_strategy(self):
        limiter = RateLimiter(strategy=RateLimitStrategy.FIXED_WINDOW)
        config = RateLimitConfig(requests_per_second=5, window_size_seconds=1)
        result = limiter.check_rate_limit("test", config)
        assert result.allowed is True


class TestAPIKeyManager:
    """Tests for APIKeyManager"""

    @pytest.fixture
    def manager(self):
        return APIKeyManager()

    def test_create_key(self, manager):
        result = manager.create_key("tenant_001", "Test Key")
        assert "key_id" in result
        assert "api_key" in result

    def test_validate_key(self, manager):
        result = manager.create_key("tenant_001", "Test Key")
        api_key = manager.validate_key(result["api_key"])
        assert api_key is not None
        assert api_key.tenant_id == "tenant_001"

    def test_validate_invalid_key(self, manager):
        api_key = manager.validate_key("invalid_key")
        assert api_key is None

    def test_revoke_key(self, manager):
        result = manager.create_key("tenant_001", "Test Key")
        revoke_result = manager.revoke_key(result["key_id"])
        assert revoke_result is True

        api_key = manager.validate_key(result["api_key"])
        assert api_key is None

    def test_get_key(self, manager):
        result = manager.create_key("tenant_001", "Test Key")
        key = manager.get_key(result["key_id"])
        assert key is not None
        assert key.name == "Test Key"

    def test_get_tenant_keys(self, manager):
        manager.create_key("tenant_001", "Key 1")
        manager.create_key("tenant_001", "Key 2")
        keys = manager.get_tenant_keys("tenant_001")
        assert len(keys) == 2

    def test_check_scope(self, manager):
        result = manager.create_key("tenant_001", "Test", scopes={"read", "write"})
        key = manager.get_key(result["key_id"])

        assert manager.check_scope(key, "read") is True
        assert manager.check_scope(key, "admin") is False

    def test_delete_key(self, manager):
        result = manager.create_key("tenant_001", "Test Key")
        delete_result = manager.delete_key(result["key_id"])
        assert delete_result is True

        key = manager.get_key(result["key_id"])
        assert key is None

    def test_key_expiration(self, manager):
        result = manager.create_key("tenant_001", "Test", expires_days=-1)
        api_key = manager.validate_key(result["api_key"])
        assert api_key is None

    def test_get_metrics(self, manager):
        manager.create_key("tenant_001", "Key 1")
        metrics = manager.get_metrics()
        assert metrics["total_keys"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
