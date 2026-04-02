"""
Day 9: Session Management Tests (F-017)

Tests for session listing, revocation, revoke-others.
"""

import hashlib
import secrets

import pytest

from backend.app.exceptions import (
    NotFoundError,
    ValidationError,
)
from backend.app.services.session_service import (
    list_sessions,
    revoke_other_sessions,
    revoke_session,
)
from database.base import SessionLocal
from database.models.core import (
    Company,
    RefreshToken,
    User,
)
from datetime import datetime, timedelta, timezone


@pytest.fixture(autouse=True)
def _setup_db():
    """Shared DB session — clean refresh tokens."""
    db = SessionLocal()
    db.query(RefreshToken).delete()
    db.commit()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def _create_user_with_sessions(db, num_sessions=3):
    """Create user with multiple sessions."""
    uid = secrets.token_hex(6)
    company = Company(
        name=f"Co-{uid}",
        industry="tech",
        subscription_tier="starter",
        subscription_status="active",
        mode="shadow",
    )
    db.add(company)
    db.flush()
    user = User(
        email=f"{uid}@test.com",
        password_hash="hash123",
        full_name=f"User-{uid}",
        role="owner",
        company_id=company.id,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()

    sessions = []
    for i in range(num_sessions):
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(
            token.encode("utf-8")
        ).hexdigest()
        rt = RefreshToken(
            user_id=user.id,
            company_id=company.id,
            token_hash=token_hash,
            device_info=f"Device-{i}",
            ip_address=f"192.168.1.{100 + i}",
            expires_at=(
                datetime.now(timezone.utc)
                + timedelta(days=7)
            ),
        )
        db.add(rt)
        db.flush()  # Ensure rt.id is available
        sessions.append({
            "id": rt.id,
            "token": token,
            "token_hash": token_hash,
        })

    db.commit()
    return user, sessions


class TestListSessions:
    """Tests for GET /api/auth/sessions."""

    def test_lists_all_sessions(self, _setup_db):
        """Should return all active sessions."""
        db = _setup_db
        user, sessions = _create_user_with_sessions(
            db, num_sessions=3
        )

        result = list_sessions(db, user.id)
        assert len(result) == 3

    def test_marks_current_session(self, _setup_db):
        """Should mark the current session."""
        db = _setup_db
        user, sessions = _create_user_with_sessions(
            db, num_sessions=2
        )

        result = list_sessions(
            db, user.id,
            current_token_hash=sessions[0]["token_hash"],
        )
        current = [s for s in result if s["is_current"]]
        assert len(current) == 1
        assert current[0]["id"] == sessions[0]["id"]

    def test_masks_ip_address(self, _setup_db):
        """IP address should be masked."""
        db = _setup_db
        user, sessions = _create_user_with_sessions(db, 1)

        result = list_sessions(db, user.id)
        assert result[0]["ip_address"].endswith(".xxx")

    def test_empty_sessions(self, _setup_db):
        """No sessions should return empty list."""
        db = _setup_db
        uid = secrets.token_hex(6)
        company = Company(
            name=f"Co-{uid}", industry="tech",
            subscription_tier="starter",
            subscription_status="active", mode="shadow",
        )
        db.add(company)
        db.flush()
        user = User(
            email=f"{uid}@test.com", password_hash="h",
            company_id=company.id, is_active=True,
        )
        db.add(user)
        db.commit()

        result = list_sessions(db, user.id)
        assert len(result) == 0


class TestRevokeSession:
    """Tests for DELETE /api/auth/sessions/{id}/revoke."""

    def test_revokes_session(self, _setup_db):
        """Should delete a specific session."""
        db = _setup_db
        user, sessions = _create_user_with_sessions(
            db, num_sessions=3
        )

        revoke_session(
            db, user.id, sessions[1]["id"]
        )
        result = list_sessions(db, user.id)
        assert len(result) == 2

    def test_cannot_revoke_current_session(self, _setup_db):
        """Cannot revoke own current session."""
        db = _setup_db
        user, sessions = _create_user_with_sessions(
            db, num_sessions=2
        )

        with pytest.raises(ValidationError):
            revoke_session(
                db, user.id,
                sessions[0]["id"],
                current_token_hash=sessions[0]["token_hash"],
            )

    def test_revoke_nonexistent_raises(self, _setup_db):
        """Non-existent session should raise 404."""
        db = _setup_db
        user, _ = _create_user_with_sessions(db, 1)

        with pytest.raises(NotFoundError):
            revoke_session(
                db, user.id, "nonexistent-id"
            )


class TestRevokeOthers:
    """Tests for DELETE /api/auth/sessions/revoke-others."""

    def test_revokes_all_others(self, _setup_db):
        """Should keep current, revoke all others."""
        db = _setup_db
        user, sessions = _create_user_with_sessions(
            db, num_sessions=4
        )

        result = revoke_other_sessions(
            db, user.id, sessions[0]["token_hash"]
        )
        assert result["count"] == 3

        remaining = list_sessions(db, user.id)
        assert len(remaining) == 1

    def test_only_session_keeps_it(self, _setup_db):
        """If only one session, count should be 0."""
        db = _setup_db
        user, sessions = _create_user_with_sessions(
            db, num_sessions=1
        )

        result = revoke_other_sessions(
            db, user.id, sessions[0]["token_hash"]
        )
        assert result["count"] == 0
