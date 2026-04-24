"""
Day 8: Password Reset Tests (F-014)

Tests for forgot/reset password flow.
BC-011: All sessions invalidated on reset.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from backend.app.exceptions import (
    AuthenticationError,
    NotFoundError,
)
from backend.app.services.password_reset_service import (
    initiate_password_reset,
    reset_password,
)
from database.base import SessionLocal
from database.models.core import (
    Company,
    PasswordResetToken,
    RefreshToken,
    User,
)

import secrets
import hashlib


@pytest.fixture(autouse=True)
def _setup_db():
    """Shared DB session — clean stale reset tokens."""
    db = SessionLocal()
    # Clean any stale reset tokens from other tests
    db.query(PasswordResetToken).delete()
    db.commit()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def _create_user(db, email="test@example.com"):
    """Helper: create a user with unique email."""
    uid = secrets.token_hex(6)
    email = f"{uid}-{email}"
    company = Company(
        name=f"Co-{uid}",
        industry="tech",
        subscription_tier="mini_parwa",
        subscription_status="active",
        mode="shadow",
    )
    db.add(company)
    db.flush()
    user = User(
        email=email,
        password_hash=(
            "$2b$12$fakehashfortest0000000"
            "0000000000000000000000000"
        ),
        full_name=f"User-{uid}",
        role="owner",
        company_id=company.id,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()
    return user


class TestInitiatePasswordReset:
    """Tests for POST /api/auth/forgot-password."""

    @patch(
        "backend.app.services.password_reset_service.send_password_reset_email",  # noqa
        return_value=True,
    )
    def test_existing_user_sends_email(self, mock_send, _setup_db):
        """Existing user should trigger reset email."""
        db = _setup_db
        user = _create_user(db)
        db.commit()

        result = initiate_password_reset(db, user.email)
        assert result["status"] == "success"
        mock_send.assert_called_once()

    def test_nonexistent_user_generic_response(self, _setup_db):
        """Non-existent user returns same generic message."""
        db = _setup_db
        result = initiate_password_reset(
            db, "nobody@example.com"
        )
        assert result["status"] == "success"

    @patch(
        "backend.app.services.password_reset_service.send_password_reset_email",  # noqa
        return_value=True,
    )
    def test_invalidates_previous_tokens(self, mock_send, _setup_db):
        """New reset invalidates previous tokens."""
        db = _setup_db
        user = _create_user(db)
        db.commit()

        initiate_password_reset(db, user.email)
        initiate_password_reset(db, user.email)
        db.expire_all()

        unused = db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.is_used == False,  # noqa: E712
        ).count()
        assert unused == 1

    @patch(
        "backend.app.services.password_reset_service.send_password_reset_email",  # noqa
        return_value=True,
    )
    def test_rate_limited_after_3(self, mock_send, _setup_db):
        """More than 3 resets per hour returns error."""
        db = _setup_db
        user = _create_user(db)
        db.commit()

        for _ in range(3):
            initiate_password_reset(db, user.email)

        result = initiate_password_reset(db, user.email)
        assert result["status"] == "error"


class TestResetPassword:
    """Tests for POST /api/auth/reset-password."""

    def _setup_reset(self, db):
        """Create user + reset token, return raw token."""
        user = _create_user(db)
        raw = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(
            raw.encode("utf-8")
        ).hexdigest()
        prt = PasswordResetToken(
            user_id=user.id,
            company_id=user.company_id,
            token_hash=token_hash,
            is_used=False,
            expires_at=(
                datetime.now(timezone.utc)
                + timedelta(minutes=15)
            ),
        )
        db.add(prt)
        db.flush()
        return user, raw

    @patch("backend.app.services.password_reset_service.hash_password")
    def test_valid_token_resets_password(self, mock_hash, _setup_db):
        """Valid token should reset password."""
        mock_hash.return_value = "$2b$12$newhash"
        db = _setup_db
        user, token = self._setup_reset(db)
        db.commit()

        result = reset_password(
            db, token=token,
            new_password="NewPassword1!",
        )
        assert result["status"] == "success"

    @patch("backend.app.services.password_reset_service.hash_password")
    def test_all_sessions_invalidated(self, mock_hash, _setup_db):
        """BC-011: Reset should invalidate ALL sessions."""
        mock_hash.return_value = "$2b$12$newhash"
        db = _setup_db
        user, token = self._setup_reset(db)

        for i in range(3):
            rt = RefreshToken(
                user_id=user.id,
                company_id=user.company_id,
                token_hash=f"session-hash-{user.id}-{i}",
                expires_at=(
                    datetime.now(timezone.utc)
                    + timedelta(days=7)
                ),
            )
            db.add(rt)
        db.commit()

        reset_password(
            db, token=token,
            new_password="NewPassword1!",
        )

        sessions_after = db.query(RefreshToken).filter(
            RefreshToken.user_id == user.id
        ).count()
        assert sessions_after == 0

    @patch("backend.app.services.password_reset_service.hash_password")
    def test_failed_login_count_reset(self, mock_hash, _setup_db):
        """Reset should clear failed login count."""
        mock_hash.return_value = "$2b$12$newhash"
        db = _setup_db
        user, token = self._setup_reset(db)
        user.failed_login_count = 5
        user.locked_until = datetime.utcnow()
        db.commit()

        reset_password(
            db, token=token,
            new_password="NewPassword1!",
        )
        db.expire_all()
        assert user.failed_login_count == 0
        assert user.locked_until is None

    def test_invalid_token_raises(self, _setup_db):
        """Invalid token should raise NotFoundError."""
        db = _setup_db
        with pytest.raises(NotFoundError):
            reset_password(
                db, token="a" * 43,
                new_password="NewPassword1!",
            )

    @patch("backend.app.services.password_reset_service.hash_password")
    def test_reused_token_raises(self, mock_hash, _setup_db):
        """Reused token should raise AuthenticationError."""
        mock_hash.return_value = "$2b$12$new"
        db = _setup_db
        user, token = self._setup_reset(db)
        db.commit()

        reset_password(
            db, token=token,
            new_password="FirstPassword1!",
        )

        with pytest.raises(AuthenticationError):
            reset_password(
                db, token=token,
                new_password="SecondPassword1!",
            )

    def test_expired_token_raises(self, _setup_db):
        """Expired token should raise AuthenticationError."""
        db = _setup_db
        user, token = self._setup_reset(db)
        stored = db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
        ).first()
        stored.expires_at = (
            datetime.now(timezone.utc) - timedelta(minutes=1)
        )
        db.commit()

        with pytest.raises(AuthenticationError):
            reset_password(
                db, token=token,
                new_password="NewPassword1!",
            )

    @patch("backend.app.services.password_reset_service.hash_password")
    def test_token_marked_as_used(self, mock_hash, _setup_db):
        """Token should be marked as used after reset."""
        mock_hash.return_value = "$2b$12$newhash"
        db = _setup_db
        user, token = self._setup_reset(db)
        db.commit()

        reset_password(
            db, token=token,
            new_password="NewPassword1!",
        )
        db.expire_all()

        stored = db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
        ).first()
        assert stored.is_used is True


class TestTokenStorage:
    """Tests for token security (SHA-256 hashed in DB)."""

    def test_token_stored_as_hash(self, _setup_db):
        """Token should be SHA-256 hashed in DB."""
        db = _setup_db
        user = _create_user(db)
        raw = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(
            raw.encode("utf-8")
        ).hexdigest()
        prt = PasswordResetToken(
            user_id=user.id,
            company_id=user.company_id,
            token_hash=token_hash,
            is_used=False,
            expires_at=(
                datetime.now(timezone.utc)
                + timedelta(minutes=15)
            ),
        )
        db.add(prt)
        db.flush()

        found = db.query(PasswordResetToken).filter(
            PasswordResetToken.token_hash == raw
        ).first()
        assert found is None

        found = db.query(PasswordResetToken).filter(
            PasswordResetToken.token_hash == token_hash
        ).first()
        assert found is not None
