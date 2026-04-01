"""
Day 7: JWT Auth Token Service Tests

Tests for JWT creation, verification, refresh token hashing.
BC-011: JWT_SECRET_KEY, HS256 algorithm, proper expiry.
"""

from datetime import datetime, timezone

import pytest

from backend.app.core.auth import (
    JWT_ALGORITHM,
    create_access_token,
    generate_refresh_token,
    get_access_token_expiry_seconds,
    hash_refresh_token,
    verify_access_token,
)
from backend.app.exceptions import AuthenticationError


class TestCreateAccessToken:
    """Tests for JWT access token creation."""

    def test_returns_non_empty_string(self):
        """Token should be a non-empty string."""
        token = create_access_token(
            user_id="user-123",
            company_id="company-456",
            email="test@example.com",
            role="owner",
        )
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_has_three_parts(self):
        """JWT should have header.payload.signature format."""
        token = create_access_token(
            user_id="user-123",
            company_id="company-456",
            email="test@example.com",
            role="owner",
        )
        parts = token.split(".")
        assert len(parts) == 3

    def test_token_contains_correct_claims(self):
        """Decoded token should contain all required claims."""
        payload = verify_access_token(
            create_access_token(
                user_id="u1",
                company_id="c1",
                email="a@b.com",
                role="admin",
            )
        )
        assert payload["sub"] == "u1"
        assert payload["company_id"] == "c1"
        assert payload["email"] == "a@b.com"
        assert payload["role"] == "admin"
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload

    def test_different_users_different_tokens(self):
        """Two different users must produce different tokens."""
        t1 = create_access_token(
            user_id="u1", company_id="c1",
            email="a@b.com", role="owner",
        )
        t2 = create_access_token(
            user_id="u2", company_id="c1",
            email="a@b.com", role="owner",
        )
        assert t1 != t2

    def test_algorithm_is_hs256(self):
        """BC-011: Must use HS256 algorithm."""
        assert JWT_ALGORITHM == "HS256"

    def test_expiry_is_set(self):
        """Token must have a future expiry time."""
        from jose import jwt
        token = create_access_token(
            user_id="u1", company_id="c1",
            email="a@b.com", role="owner",
        )
        payload = jwt.decode(
            token, _test_secret(), algorithms=["HS256"]
        )
        exp = datetime.fromtimestamp(
            payload["exp"], tz=timezone.utc
        )
        iat = datetime.fromtimestamp(
            payload["iat"], tz=timezone.utc
        )
        assert exp > iat
        # Default is 15 minutes
        delta = (exp - iat).total_seconds()
        assert delta <= 900  # 15 * 60
        assert delta > 0


class TestVerifyAccessToken:
    """Tests for JWT access token verification."""

    def test_valid_token_returns_payload(self):
        """Valid token should return decoded payload."""
        token = create_access_token(
            user_id="u1", company_id="c1",
            email="a@b.com", role="owner",
        )
        payload = verify_access_token(token)
        assert payload["sub"] == "u1"

    def test_tampered_token_raises(self):
        """Modified token should raise AuthenticationError."""
        token = create_access_token(
            user_id="u1", company_id="c1",
            email="a@b.com", role="owner",
        )
        # Tamper with the token
        parts = token.split(".")
        parts[1] = parts[1][:-1] + "X"
        tampered = ".".join(parts)

        with pytest.raises(AuthenticationError):
            verify_access_token(tampered)

    def test_wrong_secret_raises(self):
        """Token signed with different secret should fail."""
        import os
        orig = os.environ.get("JWT_SECRET_KEY")
        try:
            os.environ["JWT_SECRET_KEY"] = "secret_A"
            token = create_access_token(
                user_id="u1", company_id="c1",
                email="a@b.com", role="owner",
            )
            os.environ["JWT_SECRET_KEY"] = "secret_B"
            # Need to reimport to pick up new secret
            from importlib import reload
            import backend.app.core.auth as auth_mod
            reload(auth_mod)
            with pytest.raises(AuthenticationError):
                auth_mod.verify_access_token(token)
        finally:
            if orig:
                os.environ["JWT_SECRET_KEY"] = orig


class TestRefreshToken:
    """Tests for opaque refresh token generation and hashing."""

    def test_generate_returns_urlsafe_string(self):
        """Refresh token should be URL-safe base64 string."""
        token = generate_refresh_token()
        assert isinstance(token, str)
        assert len(token) > 0
        # Should not contain special chars that break URLs
        assert "/" not in token
        assert "+" not in token

    def test_generate_is_unique(self):
        """Each generated token should be unique."""
        t1 = generate_refresh_token()
        t2 = generate_refresh_token()
        assert t1 != t2

    def test_hash_is_deterministic(self):
        """Same token always produces same hash."""
        token = "test-refresh-token-123"
        h1 = hash_refresh_token(token)
        h2 = hash_refresh_token(token)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_hash_differs_for_different_tokens(self):
        """Different tokens must produce different hashes."""
        h1 = hash_refresh_token("token-one")
        h2 = hash_refresh_token("token-two")
        assert h1 != h2

    def test_hash_is_hex_string(self):
        """Hash should be lowercase hex string."""
        token = "test"
        h = hash_refresh_token(token)
        assert all(c in "0123456789abcdef" for c in h)


class TestGetAccessTokenExpiry:
    """Tests for access token expiry helper."""

    def test_returns_positive_int(self):
        """Expiry should be a positive integer."""
        expiry = get_access_token_expiry_seconds()
        assert isinstance(expiry, int)
        assert expiry > 0

    def test_default_is_15_minutes(self):
        """Default expiry is 15 minutes = 900 seconds."""
        expiry = get_access_token_expiry_seconds()
        assert expiry == 900


def _test_secret() -> str:
    """Get the test JWT secret from config."""
    import os
    return os.environ.get(
        "JWT_SECRET_KEY", "test_jwt_secret_key_not_prod"
    )
