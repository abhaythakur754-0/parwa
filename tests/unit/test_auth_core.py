"""
Unit tests for backend/core/auth.py - Core authentication module.
"""
import pytest
from datetime import timedelta
from unittest.mock import patch, MagicMock, AsyncMock
from uuid import uuid4, UUID

from backend.core.auth import (
    create_access_token,
    verify_token,
    hash_password,
    verify_password,
    blacklist_token,
    is_token_blacklisted,
    blacklist_token_async,
    is_token_blacklisted_async,
)


class TestCreateAccessToken:
    """Tests for create_access_token function."""

    def test_create_access_token_valid_user_id(self):
        """Test creating a token with a valid user ID."""
        user_id = uuid4()
        expires_delta = timedelta(hours=1)

        token = create_access_token(user_id, expires_delta)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_with_string_uuid(self):
        """Test creating a token with a string UUID."""
        user_id = uuid4()
        expires_delta = timedelta(hours=1)

        # Should accept string UUID and convert it
        token = create_access_token(str(user_id), expires_delta)

        assert token is not None
        assert isinstance(token, str)

    def test_create_access_token_invalid_user_id(self):
        """Test that invalid user ID raises ValueError."""
        with pytest.raises(ValueError, match="Invalid user_id format"):
            create_access_token("not-a-uuid", timedelta(hours=1))

    def test_create_access_token_none_user_id(self):
        """Test that None user ID raises ValueError."""
        with pytest.raises(ValueError, match="user_id must be a valid UUID"):
            create_access_token(None, timedelta(hours=1))

    def test_create_access_token_different_expiration(self):
        """Test creating tokens with different expiration times."""
        user_id = uuid4()

        token_1h = create_access_token(user_id, timedelta(hours=1))
        token_24h = create_access_token(user_id, timedelta(hours=24))

        # Both should be valid tokens
        assert token_1h is not None
        assert token_24h is not None
        # Different expiration should result in different tokens
        assert token_1h != token_24h


class TestVerifyToken:
    """Tests for verify_token function."""

    @patch("backend.core.auth.is_token_blacklisted")
    def test_verify_token_valid(self, mock_blacklisted):
        """Test verifying a valid token."""
        mock_blacklisted.return_value = False
        user_id = uuid4()
        token = create_access_token(user_id, timedelta(hours=1))

        payload = verify_token(token)

        assert payload is not None
        assert "sub" in payload
        assert payload["sub"] == str(user_id)

    def test_verify_token_empty_string(self):
        """Test that empty token raises ValueError."""
        with pytest.raises(ValueError, match="Token must not be empty"):
            verify_token("")

    def test_verify_token_none(self):
        """Test that None token raises ValueError."""
        with pytest.raises(ValueError, match="Token must not be empty"):
            verify_token(None)

    @patch("backend.core.auth.is_token_blacklisted")
    def test_verify_token_invalid_format(self, mock_blacklisted):
        """Test that invalid token format raises ValueError."""
        mock_blacklisted.return_value = False
        with pytest.raises(ValueError, match="Invalid token"):
            verify_token("not-a-valid-token")

    @patch("backend.core.auth.is_token_blacklisted")
    def test_verify_token_blacklisted(self, mock_blacklisted):
        """Test that blacklisted token raises ValueError."""
        mock_blacklisted.return_value = True

        user_id = uuid4()
        token = create_access_token(user_id, timedelta(hours=1))

        with pytest.raises(ValueError, match="Token has been revoked"):
            verify_token(token)


class TestHashPassword:
    """Tests for hash_password function."""

    def test_hash_password_valid(self):
        """Test hashing a valid password."""
        password = "SecurePassword123!"

        hashed = hash_password(password)

        assert hashed is not None
        assert isinstance(hashed, str)
        assert hashed != password
        assert ":" in hashed  # Hash format is 'salt:hash'

    def test_hash_password_empty(self):
        """Test that empty password raises ValueError."""
        with pytest.raises(ValueError, match="Password must not be empty"):
            hash_password("")

    def test_hash_password_none(self):
        """Test that None password raises ValueError."""
        with pytest.raises(ValueError, match="Password must not be empty"):
            hash_password(None)

    def test_hash_password_too_short(self):
        """Test that short password raises ValueError."""
        with pytest.raises(ValueError, match="Password must be at least"):
            hash_password("short")

    def test_hash_password_different_hashes(self):
        """Test that same password produces different hashes (due to salt)."""
        password = "SecurePassword123!"

        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2  # Different salts


class TestVerifyPassword:
    """Tests for verify_password function."""

    def test_verify_password_correct(self):
        """Test verifying correct password."""
        password = "SecurePassword123!"
        hashed = hash_password(password)

        result = verify_password(password, hashed)

        assert result is True

    def test_verify_password_incorrect(self):
        """Test verifying incorrect password."""
        password = "SecurePassword123!"
        wrong_password = "WrongPassword456!"
        hashed = hash_password(password)

        result = verify_password(wrong_password, hashed)

        assert result is False

    def test_verify_password_empty_plain(self):
        """Test that empty plain password returns False."""
        hashed = hash_password("SecurePassword123!")

        result = verify_password("", hashed)

        assert result is False

    def test_verify_password_empty_hashed(self):
        """Test that empty hashed password returns False."""
        result = verify_password("SecurePassword123!", "")

        assert result is False

    def test_verify_password_none_plain(self):
        """Test that None plain password returns False."""
        hashed = hash_password("SecurePassword123!")

        result = verify_password(None, hashed)

        assert result is False

    def test_verify_password_none_hashed(self):
        """Test that None hashed password returns False."""
        result = verify_password("SecurePassword123!", None)

        assert result is False


class TestBlacklistToken:
    """Tests for blacklist_token function."""

    def test_blacklist_token_empty(self):
        """Test that empty token raises ValueError."""
        with pytest.raises(ValueError, match="Token must not be empty"):
            blacklist_token("")

    def test_blacklist_token_none(self):
        """Test that None token raises ValueError."""
        with pytest.raises(ValueError, match="Token must not be empty"):
            blacklist_token(None)


class TestIsTokenBlacklisted:
    """Tests for is_token_blacklisted function."""

    def test_is_token_blacklisted_empty(self):
        """Test that empty token returns False."""
        result = is_token_blacklisted("")

        assert result is False

    def test_is_token_blacklisted_none(self):
        """Test that None token returns False."""
        result = is_token_blacklisted(None)

        assert result is False


class TestBlacklistTokenAsync:
    """Tests for blacklist_token_async function."""

    @pytest.mark.asyncio
    async def test_blacklist_token_async_success(self):
        """Test successfully blacklisting a token asynchronously."""
        mock_cache = AsyncMock()
        mock_cache.set.return_value = True
        mock_cache.close = AsyncMock()

        with patch("backend.core.auth.Cache", return_value=mock_cache):
            await blacklist_token_async("test-token-123")

            mock_cache.set.assert_called_once()
            mock_cache.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_blacklist_token_async_empty(self):
        """Test that empty token raises ValueError."""
        with pytest.raises(ValueError, match="Token must not be empty"):
            await blacklist_token_async("")

    @pytest.mark.asyncio
    async def test_blacklist_token_async_failure(self):
        """Test that cache failure raises RuntimeError."""
        mock_cache = AsyncMock()
        mock_cache.set.return_value = False  # Simulate failure
        mock_cache.close = AsyncMock()

        with patch("backend.core.auth.Cache", return_value=mock_cache):
            with pytest.raises(RuntimeError, match="Failed to blacklist token"):
                await blacklist_token_async("test-token-123")


class TestIsTokenBlacklistedAsync:
    """Tests for is_token_blacklisted_async function."""

    @pytest.mark.asyncio
    async def test_is_token_blacklisted_async_true(self):
        """Test checking if token is blacklisted returns True asynchronously."""
        mock_cache = AsyncMock()
        mock_cache.exists.return_value = True
        mock_cache.close = AsyncMock()

        with patch("backend.core.auth.Cache", return_value=mock_cache):
            result = await is_token_blacklisted_async("test-token-123")

            assert result is True
            mock_cache.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_token_blacklisted_async_false(self):
        """Test checking if token is blacklisted returns False asynchronously."""
        mock_cache = AsyncMock()
        mock_cache.exists.return_value = False
        mock_cache.close = AsyncMock()

        with patch("backend.core.auth.Cache", return_value=mock_cache):
            result = await is_token_blacklisted_async("test-token-123")

            assert result is False

    @pytest.mark.asyncio
    async def test_is_token_blacklisted_async_empty(self):
        """Test that empty token returns False asynchronously."""
        result = await is_token_blacklisted_async("")

        assert result is False

    @pytest.mark.asyncio
    async def test_is_token_blacklisted_async_error(self):
        """Test that error returns False (fail-open)."""
        mock_cache = AsyncMock()
        mock_cache.exists.side_effect = Exception("Redis error")
        mock_cache.close = AsyncMock()

        with patch("backend.core.auth.Cache", return_value=mock_cache):
            result = await is_token_blacklisted_async("test-token-123")

            # Should fail open
            assert result is False


class TestIntegration:
    """Integration tests for auth flow."""

    @patch("backend.core.auth.is_token_blacklisted")
    def test_full_auth_flow(self, mock_blacklisted):
        """Test the complete authentication flow."""
        mock_blacklisted.return_value = False
        
        # 1. Create a user ID
        user_id = uuid4()

        # 2. Hash a password
        password = "SecurePassword123!"
        hashed = hash_password(password)
        assert hashed != password

        # 3. Verify the password
        assert verify_password(password, hashed) is True
        assert verify_password("wrong-password", hashed) is False

        # 4. Create an access token
        token = create_access_token(user_id, timedelta(hours=1))
        assert token is not None

        # 5. Verify the token
        payload = verify_token(token)
        assert payload["sub"] == str(user_id)

    @patch("backend.core.auth.is_token_blacklisted")
    def test_token_blacklist_flow(self, mock_blacklisted):
        """Test token verification with blacklist check."""
        user_id = uuid4()
        token = create_access_token(user_id, timedelta(hours=1))

        # Initially not blacklisted
        mock_blacklisted.return_value = False
        payload = verify_token(token)
        assert payload["sub"] == str(user_id)

        # After blacklisting
        mock_blacklisted.return_value = True
        with pytest.raises(ValueError, match="Token has been revoked"):
            verify_token(token)

    def test_password_security_properties(self):
        """Test password hashing security properties."""
        password = "SecurePassword123!"

        # Same password produces different hashes (salting)
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2

        # Both hashes verify correctly
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True

    @patch("backend.core.auth.is_token_blacklisted")
    def test_token_has_required_claims(self, mock_blacklisted):
        """Test that token contains required claims."""
        mock_blacklisted.return_value = False
        
        user_id = uuid4()
        token = create_access_token(user_id, timedelta(hours=1))

        payload = verify_token(token)

        # Check required claims
        assert "sub" in payload
        assert "exp" in payload
        assert "iat" in payload
        assert payload["sub"] == str(user_id)
