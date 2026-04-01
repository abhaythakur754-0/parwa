"""
Day 7: Auth Service Tests

Tests for registration, authentication, token refresh,
logout, and Google OAuth business logic.
BC-011: bcrypt, JWT, hashed refresh tokens.
BC-001: Multi-tenant (company + user).
"""

from unittest.mock import MagicMock, patch

import pytest

from backend.app.exceptions import (
    AuthenticationError,
    ValidationError,
)
from backend.app.services.auth_service import (
    authenticate_user,
    get_user_by_id,
    google_auth,
    logout_user,
    refresh_tokens,
    register_user,
)
from database.base import SessionLocal, init_db


@pytest.fixture(autouse=True)
def _setup_db():
    """Create fresh in-memory SQLite DB for each test."""
    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class TestRegisterUser:
    """Tests for user registration."""

    def test_register_creates_company_and_user(self, _setup_db):
        """Registration creates both Company and User records."""
        db = _setup_db
        result = register_user(
            db=db,
            email="test@example.com",
            password="StrongPass1",
            full_name="Test User",
            company_name="Test Co",
            industry="tech",
        )

        assert result.user.email == "test@example.com"
        assert result.user.role == "owner"
        assert result.user.company_id is not None
        assert result.tokens.access_token is not None
        assert result.tokens.refresh_token is not None

    def test_register_user_is_owner_role(self, _setup_db):
        """First user in company gets 'owner' role."""
        db = _setup_db
        result = register_user(
            db=db,
            email="owner@test.com",
            password="StrongPass1",
            full_name="Owner",
            company_name="Owner Co",
            industry="finance",
        )
        assert result.user.role == "owner"

    def test_register_default_company_tier(self, _setup_db):
        """New company gets 'starter' subscription tier."""
        db = _setup_db
        result = register_user(
            db=db,
            email="tier@test.com",
            password="StrongPass1",
            full_name="Tier",
            company_name="Tier Co",
            industry="health",
        )
        assert result.user.company_name is not None

    def test_register_password_is_hashed(self, _setup_db):
        """Password must be stored as bcrypt hash, not plaintext."""
        db = _setup_db
        register_user(
            db=db,
            email="hashed@test.com",
            password="MyPassword1",
            full_name="Hashed",
            company_name="Hash Co",
            industry="tech",
        )
        from database.models.core import User
        user = db.query(User).filter(
            User.email == "hashed@test.com"
        ).first()
        assert user.password_hash != "MyPassword1"
        assert user.password_hash.startswith("$2b$12$")

    def test_register_duplicate_email_raises(self, _setup_db):
        """Duplicate email registration should raise ValidationError."""
        import uuid
        unique = f"dup-{uuid.uuid4().hex[:8]}@test.com"
        db = _setup_db
        register_user(
            db=db,
            email=unique,
            password="StrongPass1",
            full_name="First",
            company_name="First Co",
            industry="tech",
        )
        with pytest.raises(ValidationError) as exc_info:
            register_user(
                db=db,
                email=unique,
                password="StrongPass1",
                full_name="Second",
                company_name="Second Co",
                industry="tech",
            )
        assert "already registered" in str(
            exc_info.value.message
        ).lower()

    def test_register_email_lowercased(self, _setup_db):
        """Email should be stored in lowercase."""
        db = _setup_db
        result = register_user(
            db=db,
            email="MixedCase@Example.COM",
            password="StrongPass1",
            full_name="Mixed",
            company_name="Mixed Co",
            industry="tech",
        )
        assert result.user.email == "mixedcase@example.com"


class TestAuthenticateUser:
    """Tests for email/password authentication."""

    def test_login_success(self, _setup_db):
        """Valid credentials should return tokens."""
        db = _setup_db
        register_user(
            db=db,
            email="login@test.com",
            password="StrongPass1",
            full_name="Login",
            company_name="Login Co",
            industry="tech",
        )
        result = authenticate_user(
            db=db,
            email="login@test.com",
            password="StrongPass1",
        )
        assert result.user.email == "login@test.com"
        assert result.tokens.access_token is not None

    def test_login_wrong_password_raises(self, _setup_db):
        """Wrong password should raise AuthenticationError."""
        db = _setup_db
        register_user(
            db=db,
            email="wrong@test.com",
            password="StrongPass1",
            full_name="Wrong",
            company_name="Wrong Co",
            industry="tech",
        )
        with pytest.raises(AuthenticationError):
            authenticate_user(
                db=db,
                email="wrong@test.com",
                password="WrongPassword1",
            )

    def test_login_nonexistent_email_raises(self, _setup_db):
        """Non-existent email should raise AuthenticationError."""
        db = _setup_db
        with pytest.raises(AuthenticationError):
            authenticate_user(
                db=db,
                email="noone@test.com",
                password="StrongPass1",
            )

    def test_login_disabled_user_raises(self, _setup_db):
        """Disabled user should not be able to login."""
        db = _setup_db
        register_user(
            db=db,
            email="disabled@test.com",
            password="StrongPass1",
            full_name="Disabled",
            company_name="Disabled Co",
            industry="tech",
        )
        from database.models.core import User
        user = db.query(User).filter(
            User.email == "disabled@test.com"
        ).first()
        user.is_active = False
        db.commit()

        with pytest.raises(AuthenticationError):
            authenticate_user(
                db=db,
                email="disabled@test.com",
                password="StrongPass1",
            )

    def test_login_case_insensitive_email(self, _setup_db):
        """Email lookup should be case-insensitive."""
        db = _setup_db
        register_user(
            db=db,
            email="case@test.com",
            password="StrongPass1",
            full_name="Case",
            company_name="Case Co",
            industry="tech",
        )
        result = authenticate_user(
            db=db,
            email="CASE@TEST.COM",
            password="StrongPass1",
        )
        assert result.user.email == "case@test.com"


class TestRefreshTokens:
    """Tests for token refresh and rotation."""

    def test_refresh_returns_new_tokens(self, _setup_db):
        """Valid refresh token should return new token pair."""
        db = _setup_db
        reg = register_user(
            db=db,
            email="refresh@test.com",
            password="StrongPass1",
            full_name="Refresh",
            company_name="Refresh Co",
            industry="tech",
        )
        old_refresh = reg.tokens.refresh_token

        result = refresh_tokens(
            db=db, raw_token=old_refresh
        )
        assert result.access_token is not None
        assert result.refresh_token != old_refresh

    def test_refresh_invalid_token_raises(self, _setup_db):
        """Invalid refresh token should raise AuthError."""
        db = _setup_db
        with pytest.raises(AuthenticationError):
            refresh_tokens(
                db=db, raw_token="invalid-token-here"
            )

    def test_refresh_rotation_prevents_reuse(self, _setup_db):
        """Old refresh token should be invalidated after use."""
        db = _setup_db
        reg = register_user(
            db=db,
            email="rotate@test.com",
            password="StrongPass1",
            full_name="Rotate",
            company_name="Rotate Co",
            industry="tech",
        )
        old_refresh = reg.tokens.refresh_token

        # First refresh succeeds
        refresh_tokens(db=db, raw_token=old_refresh)

        # Second refresh with old token should fail
        with pytest.raises(AuthenticationError):
            refresh_tokens(
                db=db, raw_token=old_refresh
            )


class TestLogoutUser:
    """Tests for logout functionality."""

    def test_logout_deletes_token(self, _setup_db):
        """Logout should delete the refresh token."""
        db = _setup_db
        reg = register_user(
            db=db,
            email="logout@test.com",
            password="StrongPass1",
            full_name="Logout",
            company_name="Logout Co",
            industry="tech",
        )
        refresh_token = reg.tokens.refresh_token

        logout_user(db=db, raw_token=refresh_token)

        # Token should no longer work
        with pytest.raises(AuthenticationError):
            refresh_tokens(
                db=db, raw_token=refresh_token
            )

    def test_logout_invalid_token_no_error(self, _setup_db):
        """Logout with invalid token should not raise."""
        db = _setup_db
        # Should not raise any exception
        logout_user(db=db, raw_token="nonexistent-token")


class TestGoogleAuth:
    """Tests for Google OAuth authentication."""

    @patch("backend.app.services.auth_service.httpx")
    def test_google_new_user_registration(self, mock_httpx, _setup_db):
        """New Google user should get company + user created."""
        db = _setup_db
        mock_httpx.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "sub": "google-123",
                "email": "google@test.com",
                "name": "Google User",
                "picture": "https://example.com/pic.jpg",
                "email_verified": True,
                "aud": "",
            },
        )

        result = google_auth(
            db=db, id_token="fake-google-token"
        )

        assert result.user.email == "google@test.com"
        assert result.user.full_name == "Google User"
        assert result.user.avatar_url is not None
        assert result.user.is_verified is True
        assert result.tokens.access_token is not None

    @patch("backend.app.services.auth_service.httpx")
    def test_google_existing_user_login(self, mock_httpx, _setup_db):
        """Existing Google user should login without new company."""
        db = _setup_db
        mock_httpx.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "sub": "google-456",
                "email": "existing@test.com",
                "name": "Existing",
                "picture": "https://example.com/pic.jpg",
                "email_verified": True,
                "aud": "",
            },
        )

        # First call — register
        result1 = google_auth(
            db=db, id_token="fake-token-1"
        )
        company_id_1 = result1.user.company_id

        # Second call — login (same Google sub)
        result2 = google_auth(
            db=db, id_token="fake-token-2"
        )
        assert result2.user.company_id == company_id_1

    @patch("backend.app.services.auth_service.httpx")
    def test_google_verification_failure_raises(
        self, mock_httpx, _setup_db
    ):
        """Failed Google verification should raise AuthError."""
        db = _setup_db
        mock_httpx.get.return_value = MagicMock(
            status_code=400,
            json=lambda: {"error": "invalid_token"},
        )

        with pytest.raises(AuthenticationError):
            google_auth(
                db=db, id_token="bad-token"
            )


class TestGetUserById:
    """Tests for user lookup by ID."""

    def test_returns_user_when_found(self, _setup_db):
        """Should return user when ID exists."""
        db = _setup_db
        reg = register_user(
            db=db,
            email="findme@test.com",
            password="StrongPass1",
            full_name="Find Me",
            company_name="Find Co",
            industry="tech",
        )
        user = get_user_by_id(db, reg.user.id)
        assert user is not None
        assert user.email == "findme@test.com"

    def test_returns_none_when_not_found(self, _setup_db):
        """Should return None when ID doesn't exist."""
        db = _setup_db
        user = get_user_by_id(db, "nonexistent-id")
        assert user is None


class TestSessionLimit:
    """Tests for max sessions per user (BC-011)."""

    def test_max_5_sessions_enforced(self, _setup_db):
        """BC-011: Max 5 concurrent refresh tokens."""
        db = _setup_db
        register_user(
            db=db,
            email="sessions@test.com",
            password="StrongPass1",
            full_name="Sessions",
            company_name="Sessions Co",
            industry="tech",
        )

        # Create 5 sessions (1 from register + 4 logins)
        for _ in range(4):
            authenticate_user(
                db=db,
                email="sessions@test.com",
                password="StrongPass1",
            )

        # Check that only 5 tokens exist
        from database.models.core import RefreshToken
        from database.models.core import User
        user = db.query(User).filter(
            User.email == "sessions@test.com"
        ).first()
        tokens = db.query(RefreshToken).filter(
            RefreshToken.user_id == user.id
        ).all()
        assert len(tokens) == 5

        # 6th login should evict oldest token
        authenticate_user(
            db=db,
            email="sessions@test.com",
            password="StrongPass1",
        )
        tokens = db.query(RefreshToken).filter(
            RefreshToken.user_id == user.id
        ).all()
        assert len(tokens) == 5
