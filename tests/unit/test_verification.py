"""
Day 8: Email Verification Tests (F-012)

Tests for verification token creation, validation, resend.
Uses the shared DB from conftest with UUID isolation.

L17: Tokens are SHA-256 hashed in DB.
L18: Resend returns generic response (no account enum).
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from backend.app.exceptions import RateLimitError
from backend.app.services.verification_service import (
    create_verification_token,
    resend_verification_email,
    verify_email,
)
from database.base import SessionLocal
from database.models.core import (
    Company,
    User,
    VerificationToken,
)

import hashlib
import secrets


def _hash_token(token: str) -> str:
    """Hash a token to match DB storage (SHA-256)."""
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


@pytest.fixture(autouse=True)
def _setup_db():
    """Shared DB session — clean stale verification data."""
    db = SessionLocal()
    # Clean any stale verification tokens from other tests
    db.query(VerificationToken).delete()
    db.commit()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def _create_user(db, email="test@example.com", verified=False):
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
        is_verified=verified,
    )
    db.add(user)
    db.flush()
    return user


class TestVerifyEmail:
    """Tests for GET /api/auth/verify?token=..."""

    def test_valid_token_verifies_email(self, _setup_db):
        """Valid token should verify user email."""
        db = _setup_db
        user = _create_user(db)
        token = create_verification_token(db, user)
        db.commit()

        result = verify_email(db, token)
        assert result["status"] == "success"

    def test_invalid_token_returns_error(self, _setup_db):
        """Invalid token should return TOKEN_INVALID."""
        db = _setup_db
        fake = secrets.token_urlsafe(32)
        result = verify_email(db, fake)
        assert result["status"] == "error"
        assert result["error_code"] == "TOKEN_INVALID"

    def test_expired_token_returns_expired(self, _setup_db):
        """Expired token should return TOKEN_EXPIRED."""
        db = _setup_db
        user = _create_user(db)
        token = create_verification_token(db, user)

        stored = db.query(VerificationToken).filter(
            VerificationToken.user_id == user.id,
            VerificationToken.token_hash == _hash_token(token),
        ).first()
        stored.expires_at = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        )
        db.commit()

        result = verify_email(db, token)
        assert result["error_code"] == "TOKEN_EXPIRED"
        assert result["can_resend"] is True

    def test_reused_token_returns_info(self, _setup_db):
        """Re-using a used token returns 'already verified'."""
        db = _setup_db
        user = _create_user(db)
        token = create_verification_token(db, user)
        db.commit()

        verify_email(db, token)

        result = verify_email(db, token)
        assert result["status"] == "info"


class TestResendVerification:
    """Tests for POST /api/auth/resend-verification."""

    @patch("backend.app.services.verification_service.send_verification_email")
    def test_resend_success(self, mock_send, _setup_db):
        """Resend should create new token and send email."""
        mock_send.return_value = True
        db = _setup_db
        user = _create_user(db)
        db.commit()

        result = resend_verification_email(
            db, user.email
        )
        assert result["status"] == "success"

    @patch("backend.app.services.verification_service.send_verification_email")
    def test_resend_invalidates_old(self, mock_send, _setup_db):
        """Resend should invalidate previous unused tokens."""
        mock_send.return_value = True
        db = _setup_db
        user = _create_user(db)
        token1 = create_verification_token(db, user)
        db.commit()

        resend_verification_email(db, user.email)
        db.expire_all()

        stored1 = db.query(VerificationToken).filter(
            VerificationToken.user_id == user.id,
            VerificationToken.token_hash == _hash_token(token1),
        ).first()
        assert stored1.is_used is True

    def test_resend_not_found_generic(self, _setup_db):
        """Non-existent email returns generic response (L18)."""
        db = _setup_db
        result = resend_verification_email(
            db, "nobody@example.com"
        )
        assert result["status"] == "success"
        assert "account" in result["message"].lower()

    def test_resend_already_verified_generic(self, _setup_db):
        """Already verified returns generic response (L18)."""
        db = _setup_db
        user = _create_user(db, verified=True)
        db.commit()

        result = resend_verification_email(db, user.email)
        assert result["status"] == "success"

    def test_resend_rate_limited(self, _setup_db):
        """More than 3 resends per hour raises error."""
        db = _setup_db
        user = _create_user(db)
        db.commit()

        with patch(
            "backend.app.services.verification_service.send_verification_email",  # noqa
            return_value=True,
        ):
            for i in range(3):
                resend_verification_email(db, user.email)

            with pytest.raises(RateLimitError):
                resend_verification_email(db, user.email)


class TestCreateVerificationToken:
    """Tests for token creation."""

    def test_token_created(self, _setup_db):
        """Token should be created in DB (L17: hashed)."""
        db = _setup_db
        user = _create_user(db)
        token = create_verification_token(db, user)

        stored = db.query(VerificationToken).filter(
            VerificationToken.user_id == user.id,
            VerificationToken.token_hash == _hash_token(token),
        ).first()
        assert stored is not None
        assert stored.is_used is False

    def test_invalidates_previous_tokens(self, _setup_db):
        """Creating new token invalidates previous ones."""
        db = _setup_db
        user = _create_user(db)
        token1 = create_verification_token(db, user)
        token2 = create_verification_token(db, user)
        db.expire_all()

        stored1 = db.query(VerificationToken).filter(
            VerificationToken.user_id == user.id,
            VerificationToken.token_hash == _hash_token(token1),
        ).first()
        assert stored1.is_used is True

        stored2 = db.query(VerificationToken).filter(
            VerificationToken.user_id == user.id,
            VerificationToken.token_hash == _hash_token(token2),
        ).first()
        assert stored2.is_used is False
