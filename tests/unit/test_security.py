"""
Unit tests for the security module.
"""
import pytest
import time
import uuid
from datetime import timedelta
from unittest.mock import MagicMock, AsyncMock, patch

from shared.core_functions.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    sanitize_input,
    validate_email,
)
from security.rate_limiter import RateLimiter

# Test Secret Key
TEST_SECRET_KEY = "test-secret-key-for-jwt-signing"


def test_password_hashing():
    """Test that passwords hash correctly and validation works."""
    password = "MySecurePassword123!"
    hashed = hash_password(password)

    # Output should fall into salt:hash format
    assert ":" in hashed
    assert len(hashed.split(":")) == 2

    # Verification should succeed with correct password
    assert verify_password(password, hashed) is True

    # Verification should fail with incorrect password
    assert verify_password("WrongPassword123!", hashed) is False

    # Verification should fail with empty input
    assert verify_password("", hashed) is False
    assert verify_password(password, "") is False


def test_password_hashing_short_password():
    """Test that short passwords raise ValueError."""
    with pytest.raises(ValueError):
        hash_password("short")


def test_create_and_decode_access_token():
    """Test standard JWT creation and decoding."""
    data = {"sub": "user_123", "role": "admin"}
    
    # Create token
    token = create_access_token(data, TEST_SECRET_KEY, timedelta(minutes=15))
    
    assert token is not None
    assert isinstance(token, str)
    
    # Decode token
    decoded = decode_access_token(token, TEST_SECRET_KEY)
    
    assert decoded["sub"] == "user_123"
    assert decoded["role"] == "admin"
    assert "exp" in decoded
    assert "iat" in decoded


def test_decode_expired_token():
    """Test decoding an expired token raises ValueError."""
    data = {"sub": "user_123"}
    
    # Create token that expired 5 minutes ago
    token = create_access_token(data, TEST_SECRET_KEY, timedelta(minutes=-5))
    
    with pytest.raises(ValueError, match="Token has expired"):
        decode_access_token(token, TEST_SECRET_KEY)


def test_decode_invalid_token():
    """Test decoding a malformed token raises ValueError."""
    with pytest.raises(ValueError):
        decode_access_token("this.is.not.a.jwt", TEST_SECRET_KEY)


def test_sanitize_input():
    """Test input sanitization strips HTML tags and null bytes."""
    input_text = "<script>alert(1)</script> Hello World \x00"
    cleaned = sanitize_input(input_text)
    
    assert "script" not in cleaned
    assert "alert" not in cleaned
    assert "\x00" not in cleaned
    assert cleaned == "Hello World"


def test_sanitize_input_max_length():
    """Test input sanitization enforces max length."""
    long_input = "A" * 150
    with pytest.raises(ValueError, match="Input exceeds maximum length"):
        sanitize_input(long_input, max_length=100)


def test_validate_email():
    """Test email validation regex."""
    assert validate_email("test@example.com") is True
    assert validate_email("user.name+tag@domain.co.uk") is True
    
    assert validate_email("invalid-email") is False
    assert validate_email("test@.com") is False
    assert validate_email("@example.com") is False
    assert validate_email("") is False

class TestRateLimiter:
    """Tests for the Redis-backed RateLimiter."""

    @pytest.mark.asyncio
    async def test_is_allowed_increments(self):
        """Test that consecutive calls increment and allow/deny correctly."""
        with patch("shared.utils.cache.Cache._get_conn", new_callable=AsyncMock) as mock_get_conn:
            mock_redis = AsyncMock()
            mock_get_conn.return_value = mock_redis
            
            limiter = RateLimiter()
            
            # Case 1: First request (count=1)
            mock_redis.incr.return_value = 1
            allowed = await limiter.is_allowed("user_1", limit=2, window=60)
            assert allowed is True
            mock_redis.incr.assert_called_with("rate_limit:user_1")
            mock_redis.expire.assert_called_with("rate_limit:user_1", 60)
            
            # Case 2: Second request (count=2)
            mock_redis.incr.return_value = 2
            allowed = await limiter.is_allowed("user_1", limit=2, window=60)
            assert allowed is True
            
            # Case 3: Third request (count=3) - Over limit
            mock_redis.incr.return_value = 3
            allowed = await limiter.is_allowed("user_1", limit=2, window=60)
            assert allowed is False

    @pytest.mark.asyncio
    async def test_is_allowed_error_handling(self):
        """Test that the rate limiter fails open on Redis errors."""
        with patch("shared.utils.cache.Cache._get_conn", new_callable=AsyncMock) as mock_get_conn:
            mock_get_conn.side_effect = Exception("Redis connection failed")
            
            limiter = RateLimiter()
            allowed = await limiter.is_allowed("user_2", limit=2, window=60)
            # Should fail open
            assert allowed is True

class TestFeatureFlags:
    """Tests for the FeatureManager with Redis caching and tiered JSON defaults."""

    @pytest.fixture
    def mock_cache(self):
        cache = AsyncMock()
        cache.get.return_value = None
        cache.set.return_value = True
        cache.delete.return_value = True
        return cache

    @pytest.mark.asyncio
    async def test_global_tier_flags_cache_miss(self, mock_cache):
        """Test loading flags from JSON when cache is empty."""
        from security.feature_flags import FeatureManager
        manager = FeatureManager(cache=mock_cache)
        company_id = uuid.uuid4()
        
        # Mocking JSON load for 'parwa' tier
        mock_flags = {"agent_lightning": True, "sms_enabled": True}
        with patch.object(FeatureManager, "_get_tier_flags_from_json", return_value=mock_flags) as mock_json:
            enabled = await manager.is_enabled("agent_lightning", company_id, "parwa")
            
            assert enabled is True
            mock_json.assert_called_once_with("parwa")
            # Verify it tried to cache it
            mock_cache.set.assert_called_with("ff:tier:parwa", mock_flags, expire=3600)

    @pytest.mark.asyncio
    async def test_global_tier_flags_cache_hit(self, mock_cache):
        """Test loading flags from cache directly."""
        from security.feature_flags import FeatureManager
        mock_cache.get.side_effect = [
            None, # Override check
            {"agent_lightning": False} # Tier cache hit
        ]
        
        manager = FeatureManager(cache=mock_cache)
        company_id = uuid.uuid4()
        
        enabled = await manager.is_enabled("agent_lightning", company_id, "parwa")
        assert enabled is False
        mock_cache.get.assert_any_call("ff:tier:parwa")

    @pytest.mark.asyncio
    async def test_company_override(self, mock_cache):
        """Test that per-company override takes precedence."""
        from security.feature_flags import FeatureManager
        company_id = uuid.uuid4()
        feature = "agent_lightning"
        
        # Mock override exists in Redis
        mock_cache.get.return_value = True # Override says True
        
        manager = FeatureManager(cache=mock_cache)
        # Even if tier says false (not called due to override hit), it should be True
        enabled = await manager.is_enabled(feature, company_id, "mini")
        
        assert enabled is True
        mock_cache.get.assert_called_with(f"ff:override:{company_id}:{feature}")

    @pytest.mark.asyncio
    async def test_set_override(self, mock_cache):
        """Test setting an override."""
        from security.feature_flags import FeatureManager
        manager = FeatureManager(cache=mock_cache)
        company_id = uuid.uuid4()
        await manager.set_override(company_id, "video_enabled", True)
        
        mock_cache.set.assert_called_with(f"ff:override:{company_id}:video_enabled", True, expire=86400)
