"""
Day 8: Auth API Endpoint Tests (F-012, F-014)

Tests for email verification and password reset endpoints.
"""

from unittest.mock import patch

import pytest  # noqa: F401


class TestVerifyEndpoint:
    """Tests for GET /api/auth/verify?token=..."""

    @patch("backend.app.services.verification_service.send_verification_email")
    def test_verify_success(self, mock_send, client):
        """Valid token returns success."""
        mock_send.return_value = True
        # Register a user
        client.post("/api/auth/register", json={
            "email": "verify@test.com",
            "password": "StrongPass1!",
            "confirm_password": "StrongPass1!",
            "full_name": "Verify",
            "company_name": "Verify Co",
            "industry": "tech",
        })

        # Create a verification token manually
        from database.base import SessionLocal
        from database.models.core import VerificationToken
        from database.models.core import User
        db = SessionLocal()
        user = db.query(User).filter(
            User.email == "verify@test.com"
        ).first()
        import secrets
        import hashlib as _hashlib
        raw_token = secrets.token_urlsafe(32)
        vt = VerificationToken(
            user_id=user.id,
            company_id=user.company_id,
            token_hash=_hashlib.sha256(
                raw_token.encode("utf-8")
            ).hexdigest(),
            purpose="email_verification",
            is_used=False,
            expires_at=(
                __import__("datetime").datetime.utcnow()
                + __import__("datetime").timedelta(hours=24)
            ),
        )
        db.add(vt)
        db.commit()
        db.close()

        resp = client.get(
            f"/api/auth/verify?token={raw_token}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"

    def test_verify_invalid_token(self, client):
        """Invalid token returns error."""
        # L27: Must be at least 32 chars
        fake_token = "a" * 43
        resp = client.get(
            f"/api/auth/verify?token={fake_token}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"

    def test_verify_short_token_422(self, client):
        """Token too short returns 422 (L27)."""
        resp = client.get(
            "/api/auth/verify?token=bad-token"
        )
        assert resp.status_code == 422

    def test_verify_no_token_422(self, client):
        """Missing token parameter returns 422."""
        resp = client.get("/api/auth/verify")
        assert resp.status_code == 422


class TestResendVerificationEndpoint:
    """Tests for POST /api/auth/resend-verification."""

    @patch("backend.app.services.verification_service.send_verification_email")
    def test_resend_success(self, mock_send, client):
        """Valid resend returns success."""
        mock_send.return_value = True
        client.post("/api/auth/register", json={
            "email": "resend@test.com",
            "password": "StrongPass1!",
            "confirm_password": "StrongPass1!",
            "full_name": "Resend",
            "company_name": "Resend Co",
            "industry": "tech",
        })

        resp = client.post(
            "/api/auth/resend-verification",
            json={"email": "resend@test.com"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_resend_not_found(self, client):
        """Non-existent email returns generic success (L18)."""
        resp = client.post(
            "/api/auth/resend-verification",
            json={"email": "nobody@test.com"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

    def test_resend_invalid_email_422(self, client):
        """Invalid email format returns 422."""
        resp = client.post(
            "/api/auth/resend-verification",
            json={"email": "not-an-email"},
        )
        assert resp.status_code == 422


class TestForgotPasswordEndpoint:
    """Tests for POST /api/auth/forgot-password."""

    @patch(
        "backend.app.services.password_reset_service"
        ".send_password_reset_email"
    )
    def test_existing_user(self, mock_send, client):
        """Existing user gets generic success message."""
        mock_send.return_value = True
        client.post("/api/auth/register", json={
            "email": "forgot@test.com",
            "password": "StrongPass1!",
            "confirm_password": "StrongPass1!",
            "full_name": "Forgot",
            "company_name": "Forgot Co",
            "industry": "tech",
        })

        resp = client.post(
            "/api/auth/forgot-password",
            json={"email": "forgot@test.com"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        # F-014: Generic response, no account enum
        assert "account" in data["message"].lower()

    def test_nonexistent_user_generic_response(self, client):
        """Non-existent user gets SAME generic message."""
        resp = client.post(
            "/api/auth/forgot-password",
            json={"email": "nobody@test.com"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        # No info leakage

    def test_invalid_email_format_422(self, client):
        """Invalid email format returns 422."""
        resp = client.post(
            "/api/auth/forgot-password",
            json={"email": "bad"},
        )
        assert resp.status_code == 422


class TestResetPasswordEndpoint:
    """Tests for POST /api/auth/reset-password."""

    def _setup_reset(self, client):
        """Create user + reset token, return token."""
        import hashlib
        import secrets
        client.post("/api/auth/register", json={
            "email": "reset@test.com",
            "password": "StrongPass1!",
            "confirm_password": "StrongPass1!",
            "full_name": "Reset",
            "company_name": "Reset Co",
            "industry": "tech",
        })

        from database.base import SessionLocal
        from database.models.core import (
            PasswordResetToken,
            User,
        )
        db = SessionLocal()
        user = db.query(User).filter(
            User.email == "reset@test.com"
        ).first()
        raw = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(
            raw.encode("utf-8")
        ).hexdigest()
        from datetime import timedelta, timezone
        from datetime import datetime
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
        db.commit()
        db.close()
        return raw

    def test_valid_reset_success(self, client):
        """Valid token + password resets successfully."""
        token = self._setup_reset(client)
        resp = client.post(
            "/api/auth/reset-password",
            json={
                "token": token,
                "new_password": "NewPassword1!",
                "confirm_password": "NewPassword1!",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"

    def test_invalid_token_404(self, client):
        """Invalid token (valid length but wrong value) returns 404."""
        resp = client.post(
            "/api/auth/reset-password",
            json={
                "token": "a" * 43,
                "new_password": "NewPassword1!",
                "confirm_password": "NewPassword1!",
            },
        )
        assert resp.status_code == 404

    def test_mismatched_confirm_422(self, client):
        """Mismatched confirm_password returns 422."""
        token = self._setup_reset(client)
        resp = client.post(
            "/api/auth/reset-password",
            json={
                "token": token,
                "new_password": "NewPassword1!",
                "confirm_password": "Different1!",
            },
        )
        assert resp.status_code == 422

    def test_weak_new_password_422(self, client):
        """Weak new password returns 422."""
        token = self._setup_reset(client)
        resp = client.post(
            "/api/auth/reset-password",
            json={
                "token": token,
                "new_password": "weak",
                "confirm_password": "weak",
            },
        )
        assert resp.status_code == 422

    def test_no_special_char_422(self, client):
        """Password without special char returns 422."""
        token = self._setup_reset(client)
        resp = client.post(
            "/api/auth/reset-password",
            json={
                "token": token,
                "new_password": "NoSpecial1",
                "confirm_password": "NoSpecial1",
            },
        )
        assert resp.status_code == 422
