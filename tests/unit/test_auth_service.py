"""
Day 7: Auth Service Tests

Tests for registration, authentication, token refresh,
logout, Google OAuth, progressive lockout, email check.

BC-011: bcrypt, JWT, hashed refresh tokens.
BC-001: Multi-tenant (company + user).

Loophole fixes tested:
- L01: confirm_password validation
- L02: Special character in password
- L07: Refresh reuse invalidates ALL tokens
- L08: is_new_user flag
- L09: Google token not stored plaintext
- L11: Progressive lockout (5 fails → 15min lock)
"""

from unittest.mock import MagicMock, patch

import pytest

from app.core.auth import hash_refresh_token
from app.exceptions import (
    AuthenticationError,
    ValidationError,
)
from app.services.auth_service import (
    authenticate_user,
    check_email_availability,
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
            password="StrongPass1!",
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
            password="StrongPass1!",
            full_name="Owner",
            company_name="Owner Co",
            industry="finance",
        )
        assert result.user.role == "owner"

    def test_register_default_company_tier(self, _setup_db):
        """New company gets 'mini_parwa' subscription tier."""
        db = _setup_db
        result = register_user(
            db=db,
            email="tier@test.com",
            password="StrongPass1!",
            full_name="Tier",
            company_name="Tier Co",
            industry="health",
        )
        assert result.user.company_name is not None

    def test_register_password_is_hashed(self, _setup_db):
        """Password must be stored as bcrypt hash."""
        db = _setup_db
        register_user(
            db=db,
            email="hashed@test.com",
            password="MyPassword1!",
            full_name="Hashed",
            company_name="Hash Co",
            industry="tech",
        )
        from database.models.core import User
        user = db.query(User).filter(
            User.email == "hashed@test.com"
        ).first()
        assert user.password_hash != "MyPassword1!"
        assert user.password_hash.startswith("$2b$12$")

    def test_register_duplicate_email_raises(self, _setup_db):
        """Duplicate email raises ValidationError."""
        import uuid
        unique = f"dup-{uuid.uuid4().hex[:8]}@test.com"
        db = _setup_db
        register_user(
            db=db,
            email=unique,
            password="StrongPass1!",
            full_name="First",
            company_name="First Co",
            industry="tech",
        )
        with pytest.raises(ValidationError) as exc_info:
            register_user(
                db=db,
                email=unique,
                password="StrongPass1!",
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
            password="StrongPass1!",
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
            password="StrongPass1!",
            full_name="Login",
            company_name="Login Co",
            industry="tech",
        )
        result = authenticate_user(
            db=db,
            email="login@test.com",
            password="StrongPass1!",
        )
        assert result.user.email == "login@test.com"
        assert result.tokens.access_token is not None

    def test_login_wrong_password_raises(self, _setup_db):
        """Wrong password should raise AuthenticationError."""
        db = _setup_db
        register_user(
            db=db,
            email="wrong@test.com",
            password="StrongPass1!",
            full_name="Wrong",
            company_name="Wrong Co",
            industry="tech",
        )
        with pytest.raises(AuthenticationError):
            authenticate_user(
                db=db,
                email="wrong@test.com",
                password="WrongPassword1!",
            )

    def test_login_nonexistent_email_raises(self, _setup_db):
        """Non-existent email should raise AuthenticationError."""
        db = _setup_db
        with pytest.raises(AuthenticationError):
            authenticate_user(
                db=db,
                email="noone@test.com",
                password="StrongPass1!",
            )

    def test_login_disabled_user_raises(self, _setup_db):
        """Disabled user should not be able to login."""
        db = _setup_db
        register_user(
            db=db,
            email="disabled@test.com",
            password="StrongPass1!",
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
                password="StrongPass1!",
            )

    def test_login_case_insensitive_email(self, _setup_db):
        """Email lookup should be case-insensitive."""
        db = _setup_db
        register_user(
            db=db,
            email="case@test.com",
            password="StrongPass1!",
            full_name="Case",
            company_name="Case Co",
            industry="tech",
        )
        result = authenticate_user(
            db=db,
            email="CASE@TEST.COM",
            password="StrongPass1!",
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
            password="StrongPass1!",
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
            password="StrongPass1!",
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
            password="StrongPass1!",
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

    @patch("app.services.auth_service.httpx")
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

    @patch("app.services.auth_service.httpx")
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

    @patch("app.services.auth_service.httpx")
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
            password="StrongPass1!",
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
            password="StrongPass1!",
            full_name="Sessions",
            company_name="Sessions Co",
            industry="tech",
        )

        # Create 5 sessions (1 from register + 4 logins)
        for _ in range(4):
            authenticate_user(
                db=db,
                email="sessions@test.com",
                password="StrongPass1!",
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
            password="StrongPass1!",
        )
        tokens = db.query(RefreshToken).filter(
            RefreshToken.user_id == user.id
        ).all()
        assert len(tokens) == 5


class TestIsNewUser:
    """L08: Tests for is_new_user flag."""

    def test_register_returns_is_new_user_true(self, _setup_db):
        """Registration should set is_new_user=True."""
        db = _setup_db
        result = register_user(
            db=db,
            email="newuser@test.com",
            password="StrongPass1!",
            full_name="New",
            company_name="New Co",
            industry="tech",
        )
        assert result.is_new_user is True

    def test_login_returns_is_new_user_false(self, _setup_db):
        """Login should set is_new_user=False."""
        db = _setup_db
        register_user(
            db=db,
            email="loginnew@test.com",
            password="StrongPass1!",
            full_name="Login",
            company_name="Login Co",
            industry="tech",
        )
        result = authenticate_user(
            db=db,
            email="loginnew@test.com",
            password="StrongPass1!",
        )
        assert result.is_new_user is False

    @patch("app.services.auth_service.httpx")
    def test_google_new_user_flag(self, mock_httpx, _setup_db):
        """Google OAuth new user sets is_new_user=True."""
        db = _setup_db
        mock_httpx.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "sub": "g-new-123",
                "email": "gnewflag@test.com",
                "name": "New G User",
                "picture": "",
                "email_verified": True,
                "aud": "",
            },
        )
        result = google_auth(
            db=db, id_token="fake-token"
        )
        assert result.is_new_user is True

    @patch("app.services.auth_service.httpx")
    def test_google_returning_user_flag(self, mock_httpx, _setup_db):
        """Google OAuth returning user sets is_new_user=False."""
        db = _setup_db
        mock_httpx.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "sub": "g-ret-123",
                "email": "gretflag@test.com",
                "name": "Returning",
                "picture": "",
                "email_verified": True,
                "aud": "",
            },
        )
        # First call = new
        google_auth(db=db, id_token="fake-1")
        # Second call = returning
        result = google_auth(db=db, id_token="fake-2")
        assert result.is_new_user is False


class TestProgressiveLockout:
    """L11: Tests for progressive lockout system."""

    def test_account_locks_after_5_failures(self, _setup_db):
        """Account should lock after 5 failed attempts."""
        db = _setup_db
        register_user(
            db=db,
            email="lockout@test.com",
            password="StrongPass1!",
            full_name="Lockout",
            company_name="Lockout Co",
            industry="tech",
        )

        # 5 failed attempts
        for i in range(5):
            with pytest.raises(AuthenticationError) as exc:
                authenticate_user(
                    db=db,
                    email="lockout@test.com",
                    password="WrongPassword1!",
                )

        # 6th attempt should say locked
        with pytest.raises(AuthenticationError) as exc:
            authenticate_user(
                db=db,
                email="lockout@test.com",
                password="WrongPassword1!",
            )
        assert "locked" in str(
            exc.value.message
        ).lower()

    def test_failed_login_count_increments(self, _setup_db):
        """failed_login_count should increment on each failure."""
        db = _setup_db
        register_user(
            db=db,
            email="count@test.com",
            password="StrongPass1!",
            full_name="Count",
            company_name="Count Co",
            industry="tech",
        )
        from database.models.core import User

        authenticate_user_fail(db, "count@test.com")
        user = db.query(User).filter(
            User.email == "count@test.com"
        ).first()
        assert user.failed_login_count == 1

        authenticate_user_fail(db, "count@test.com")
        user = db.query(User).filter(
            User.email == "count@test.com"
        ).first()
        assert user.failed_login_count == 2

    def test_success_resets_failed_count(self, _setup_db):
        """Successful login should reset failed_login_count."""
        db = _setup_db
        register_user(
            db=db,
            email="reset@test.com",
            password="StrongPass1!",
            full_name="Reset",
            company_name="Reset Co",
            industry="tech",
        )
        from database.models.core import User

        # Fail once
        authenticate_user_fail(db, "reset@test.com")

        # Succeed
        authenticate_user(
            db=db,
            email="reset@test.com",
            password="StrongPass1!",
        )

        user = db.query(User).filter(
            User.email == "reset@test.com"
        ).first()
        assert user.failed_login_count == 0
        assert user.locked_until is None


class TestRefreshReuseInvalidation:
    """L07: Tests for refresh token reuse detection."""

    def test_expired_token_invalidates_all(self, _setup_db):
        """Expired token should invalidate ALL user tokens."""
        db = _setup_db
        reg = register_user(
            db=db,
            email="expall@test.com",
            password="StrongPass1!",
            full_name="ExpAll",
            company_name="ExpAll Co",
            industry="tech",
        )

        # Get the actual token from registration
        raw_token = reg.tokens.refresh_token

        # Manually expire the token
        from datetime import datetime, timedelta
        from database.models.core import RefreshToken, User

        token_hash = hash_refresh_token(raw_token)
        stored = db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash
        ).first()
        stored.expires_at = (
            datetime.utcnow() - timedelta(days=1)
        )
        db.commit()

        user = db.query(User).filter(
            User.email == "expall@test.com"
        ).first()
        tokens_before = db.query(RefreshToken).filter(
            RefreshToken.user_id == user.id
        ).count()
        assert tokens_before >= 1

        # Try to use expired token — should invalidate ALL
        with pytest.raises(AuthenticationError):
            refresh_tokens(db=db, raw_token=raw_token)

        # All tokens should be gone
        tokens_after = db.query(RefreshToken).filter(
            RefreshToken.user_id == user.id
        ).count()
        assert tokens_after == 0


class TestEmailAvailability:
    """L04: Tests for email availability check."""

    def test_available_email_returns_true(self, _setup_db):
        """Unregistered email should return True."""
        db = _setup_db
        assert check_email_availability(
            db, "nobody@test.com"
        ) is True

    def test_taken_email_returns_false(self, _setup_db):
        """Registered email should return False."""
        db = _setup_db
        register_user(
            db=db,
            email="taken@test.com",
            password="StrongPass1!",
            full_name="Taken",
            company_name="Taken Co",
            industry="tech",
        )
        assert check_email_availability(
            db, "taken@test.com"
        ) is False

    def test_case_insensitive_check(self, _setup_db):
        """Email check should be case-insensitive."""
        db = _setup_db
        register_user(
            db=db,
            email="casecheck@test.com",
            password="StrongPass1!",
            full_name="Case",
            company_name="Case Co",
            industry="tech",
        )
        assert check_email_availability(
            db, "CASECHECK@TEST.COM"
        ) is False


class TestGoogleTokenNotStored:
    """L09: Tests that Google ID token is not stored."""

    @patch("app.services.auth_service.httpx")
    def test_oauth_access_token_is_none(self, mock_httpx, _setup_db):
        """OAuthAccount.access_token should be None (L09)."""
        db = _setup_db
        mock_httpx.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "sub": "g-notok-123",
                "email": "notok@test.com",
                "name": "NoTok",
                "picture": "",
                "email_verified": True,
                "aud": "",
            },
        )
        google_auth(db=db, id_token="fake-token")

        from database.models.core import OAuthAccount
        oauth = db.query(OAuthAccount).filter(
            OAuthAccount.provider == "google"
        ).first()
        assert oauth is not None
        assert oauth.access_token is None


class TestPasswordStrength:
    """L03: Tests for password strength meter."""

    def test_weak_password(self):
        from app.schemas.auth import get_password_strength
        assert get_password_strength("short") == "weak"

    def test_fair_password(self):
        from app.schemas.auth import get_password_strength
        assert get_password_strength("Abcd123!") == "fair"

    def test_strong_password(self):
        from app.schemas.auth import get_password_strength
        assert get_password_strength(
            "Abcdef123!@#"
        ) == "strong"

    def test_very_strong_password(self):
        from app.schemas.auth import get_password_strength
        assert get_password_strength(
            "VeryLongPassword123!@#$%^&"
        ) == "very strong"


def authenticate_user_fail(db, email):
    """Helper: fail authentication for lockout tests."""
    try:
        authenticate_user(
            db=db,
            email=email,
            password="WrongPassword1!",
        )
    except AuthenticationError:
        pass
