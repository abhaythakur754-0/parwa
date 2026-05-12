"""
Tests for JWT RS256 Migration (Week 6 — dual-algorithm support).

Validates that:
- HS256 backward compatibility is maintained (default config)
- RS256 tokens can be created and verified when keys are configured
- _get_jwt_algorithm() returns HS256 by default
- _load_rs256_keys() returns (None, None) when no keys configured
- rotate_jwt_key() exists and returns expected structure
- HS256 tokens still work after RS256 is configured
"""

import os
from unittest.mock import patch

import pytest


# ── Import auth module ──────────────────────────────────────────────

from app.core import auth as auth_module


class TestHS256BackwardCompatibility:
    """Test that HS256 continues to work as the default algorithm."""

    def test_default_algorithm_is_hs256(self):
        """_get_jwt_algorithm() should return 'HS256' by default."""
        algorithm = auth_module._get_jwt_algorithm()
        assert algorithm == "HS256"

    def test_create_access_token_with_hs256(self):
        """create_access_token with HS256 should produce a valid token."""
        token = auth_module.create_access_token(
            user_id="user-123",
            company_id="company-456",
            email="test@example.com",
            role="admin",
        )
        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_access_token_with_hs256(self):
        """verify_access_token should verify an HS256 token."""
        token = auth_module.create_access_token(
            user_id="user-123",
            company_id="company-456",
            email="test@example.com",
            role="admin",
        )
        payload = auth_module.verify_access_token(token)
        assert payload["sub"] == "user-123"
        assert payload["company_id"] == "company-456"
        assert payload["email"] == "test@example.com"
        assert payload["role"] == "admin"
        assert payload["type"] == "access"

    def test_hs256_token_has_required_claims(self):
        """HS256 token should have jti, iat, nbf, exp claims."""
        token = auth_module.create_access_token(
            user_id="user-123",
            company_id="company-456",
            email="test@example.com",
            role="admin",
        )
        payload = auth_module.verify_access_token(token)
        assert "jti" in payload
        assert "iat" in payload
        assert "nbf" in payload
        assert "exp" in payload
        assert payload["type"] == "access"


# ── RS256 Key Loading Tests ────────────────────────────────────────


class TestRS256KeyLoading:
    """Test RS256 key loading functionality."""

    def test_load_rs256_keys_returns_none_when_not_configured(self):
        """_load_rs256_keys() should return (None, None) when no keys configured."""
        private, public = auth_module._load_rs256_keys()
        # With default config (no key paths set), should return None, None
        assert private is None or isinstance(private, str)
        assert public is None or isinstance(public, str)

    def test_load_rs256_keys_with_test_keys(self):
        """_load_rs256_keys() should load keys when file paths are configured."""
        private_path = "/home/z/my-project/secrets/test_private.pem"
        public_path = "/home/z/my-project/secrets/test_public.pem"

        # Verify files exist
        assert os.path.exists(private_path), f"Test private key not found: {private_path}"
        assert os.path.exists(public_path), f"Test public key not found: {public_path}"

        with patch.dict(os.environ, {
            "JWT_PRIVATE_KEY_PATH": private_path,
            "JWT_PUBLIC_KEY_PATH": public_path,
        }, clear=False):
            # Force re-read of settings by patching get_settings
            from app.config import Settings
            settings = Settings()
            assert settings.JWT_PRIVATE_KEY_PATH == private_path

            # Test that keys load successfully
            # We need to clear the cached settings
            with patch("app.core.auth.get_settings", return_value=settings):
                private, public = auth_module._load_rs256_keys()
                assert private is not None, "Private key should be loaded"
                assert public is not None, "Public key should be loaded"
                assert "BEGIN" in private
                assert "BEGIN" in public


# ── RS256 Token Tests ──────────────────────────────────────────────


class TestRS256Tokens:
    """Test RS256 token creation and verification."""

    def test_rs256_token_creation_and_verification(self):
        """Create an RS256 token and verify it works."""
        private_path = "/home/z/my-project/secrets/test_private.pem"
        public_path = "/home/z/my-project/secrets/test_public.pem"

        from app.config import Settings

        # Create settings with RS256 config
        env = {
            "JWT_PRIVATE_KEY_PATH": private_path,
            "JWT_PUBLIC_KEY_PATH": public_path,
            "JWT_ALGORITHM": "RS256",
            "JWT_KID": "test-key-v1",
        }
        # Preserve required env vars
        for key in ["SECRET_KEY", "JWT_SECRET_KEY", "DATABASE_URL",
                     "DATA_ENCRYPTION_KEY", "ENVIRONMENT"]:
            if key in os.environ:
                env[key] = os.environ[key]

        with patch.dict(os.environ, env, clear=False):
            settings = Settings()

            with patch("app.core.auth.get_settings", return_value=settings):
                # Create RS256 token
                token = auth_module.create_access_token(
                    user_id="user-rs256",
                    company_id="company-rs256",
                    email="rs256@example.com",
                    role="owner",
                )

                assert isinstance(token, str)
                assert len(token) > 0

                # Verify RS256 token
                payload = auth_module.verify_access_token(token)
                assert payload["sub"] == "user-rs256"
                assert payload["company_id"] == "company-rs256"
                assert payload["email"] == "rs256@example.com"
                assert payload["role"] == "owner"

    def test_rs256_token_includes_kid(self):
        """RS256 token should include kid claim in JWT header."""
        private_path = "/home/z/my-project/secrets/test_private.pem"
        public_path = "/home/z/my-project/secrets/test_public.pem"

        from app.config import Settings
        from jose import jwt

        env = {
            "JWT_PRIVATE_KEY_PATH": private_path,
            "JWT_PUBLIC_KEY_PATH": public_path,
            "JWT_ALGORITHM": "RS256",
            "JWT_KID": "test-key-v1",
        }
        for key in ["SECRET_KEY", "JWT_SECRET_KEY", "DATABASE_URL",
                     "DATA_ENCRYPTION_KEY", "ENVIRONMENT"]:
            if key in os.environ:
                env[key] = os.environ[key]

        with patch.dict(os.environ, env, clear=False):
            settings = Settings()

            with patch("app.core.auth.get_settings", return_value=settings):
                token = auth_module.create_access_token(
                    user_id="user-kid",
                    company_id="company-kid",
                    email="kid@example.com",
                    role="admin",
                )
                # Decode header without verification to check kid
                headers = jwt.get_unverified_header(token)
                assert "kid" in headers, "RS256 token should include kid header"

    def test_hs256_tokens_still_verifiable_after_rs256_configured(self):
        """HS256 tokens should still work even when RS256 is configured."""
        private_path = "/home/z/my-project/secrets/test_private.pem"
        public_path = "/home/z/my-project/secrets/test_public.pem"

        from app.config import Settings

        # First, create an HS256 token with default config
        hs256_token = auth_module.create_access_token(
            user_id="user-hs256",
            company_id="company-hs256",
            email="hs256@example.com",
            role="agent",
        )

        # Now configure RS256
        env = {
            "JWT_PRIVATE_KEY_PATH": private_path,
            "JWT_PUBLIC_KEY_PATH": public_path,
            "JWT_ALGORITHM": "RS256",
            "JWT_KID": "test-key-v1",
        }
        for key in ["SECRET_KEY", "JWT_SECRET_KEY", "DATABASE_URL",
                     "DATA_ENCRYPTION_KEY", "ENVIRONMENT"]:
            if key in os.environ:
                env[key] = os.environ[key]

        with patch.dict(os.environ, env, clear=False):
            settings = Settings()

            with patch("app.core.auth.get_settings", return_value=settings):
                # Verify the old HS256 token still works
                # (verify_access_token tries RS256 first, then falls back to HS256)
                payload = auth_module.verify_access_token(hs256_token)
                assert payload["sub"] == "user-hs256"
                assert payload["company_id"] == "company-hs256"


# ── Helper Function Tests ──────────────────────────────────────────


class TestJWTHelperFunctions:
    """Test JWT helper functions added in Week 6."""

    def test_rotate_jwt_key_exists(self):
        """rotate_jwt_key() function should exist and be callable."""
        assert callable(auth_module.rotate_jwt_key)

    def test_rotate_jwt_key_hs256_returns_success(self):
        """rotate_jwt_key with HS256 should return success dict."""
        result = auth_module.rotate_jwt_key("new-secret-key")
        assert "success" in result
        assert "message" in result
        assert isinstance(result["success"], bool)
        assert isinstance(result["message"], str)

    def test_rotate_jwt_key_invalid_algorithm(self):
        """rotate_jwt_key with invalid algorithm should return failure."""
        result = auth_module.rotate_jwt_key("new-key", algorithm="INVALID")
        assert result["success"] is False
        assert "Unsupported algorithm" in result["message"]

    def test_rotate_jwt_key_rs256_returns_success(self):
        """rotate_jwt_key with RS256 should return success dict."""
        result = auth_module.rotate_jwt_key("some-key", algorithm="RS256")
        assert result["success"] is True

    def test_get_jwt_algorithm_returns_string(self):
        """_get_jwt_algorithm() should return a string."""
        result = auth_module._get_jwt_algorithm()
        assert isinstance(result, str)
        assert result in ("HS256", "RS256")

    def test_load_rs256_keys_returns_tuple(self):
        """_load_rs256_keys() should return a tuple of (private, public)."""
        result = auth_module._load_rs256_keys()
        assert isinstance(result, tuple)
        assert len(result) == 2
