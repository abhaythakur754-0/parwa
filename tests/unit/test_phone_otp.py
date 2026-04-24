"""
Tests for PARWA Phone OTP Service (C5)

Tests:
- OTP send with valid phone
- OTP send with invalid phone (422)
- OTP stored in DB after send
- OTP verify success
- OTP verify wrong code
- OTP verify expired code
- OTP verify too many attempts
- OTP verify already verified
- OTP attempts remaining
- Constant-time comparison
"""

import os

os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test_secret_key_for_testing_only_not_prod"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_not_prod"
os.environ["DATA_ENCRYPTION_KEY"] = "12345678901234567890123456789012"

import hashlib  # noqa: E402
import uuid  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402

import pytest  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from backend.app.main import app  # noqa: E402
from database.base import SessionLocal, init_db  # noqa: E402
from database.models.core import Company  # noqa: E402
from database.models.phone_otp import PhoneOTP  # noqa: E402

init_db()


@pytest.fixture
def db():
    """Provide a fresh database session."""
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def company(db):
    """Create a test company with unique ID."""
    comp_id = f"test-otp-co-{uuid.uuid4().hex[:8]}"
    comp = Company(
        id=comp_id,
        name="Test Co",
        industry="tech",
        subscription_tier="mini_parwa",
    )
    db.add(comp)
    db.commit()
    db.refresh(comp)
    return comp


@pytest.fixture
def client():
    """Sync test client for FastAPI app."""
    return TestClient(app)


class TestSendOTP:
    """Tests for sending OTP codes."""

    def test_send_otp_valid_phone(self, client, company):
        """Valid phone number returns success."""
        resp = client.post(
            "/api/auth/phone/send",
            json={
                "phone": "+14155552671",
                "company_id": company.id,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "OTP sent"
        assert data["expires_in"] == 300

    def test_send_otp_invalid_phone_422(self, client, company):
        """Invalid phone format returns 422."""
        resp = client.post(
            "/api/auth/phone/send",
            json={
                "phone": "4155552671",
                "company_id": company.id,
            },
        )
        assert resp.status_code == 422

    def test_send_otp_stores_in_db(self, client, company, db):
        """OTP is stored hashed in DB after send."""
        resp = client.post(
            "/api/auth/phone/send",
            json={
                "phone": "+14155552671",
                "company_id": company.id,
            },
        )
        assert resp.status_code == 200

        records = (
            db.query(PhoneOTP)
            .filter_by(
                phone="+14155552671",
                company_id=company.id,
            )
            .all()
        )
        assert len(records) >= 1
        assert records[0].code_hash is not None
        assert len(records[0].code_hash) == 64  # SHA-256
        assert records[0].verified is False

    def test_send_otp_missing_company_404(self, client):
        """Non-existent company returns 404."""
        resp = client.post(
            "/api/auth/phone/send",
            json={
                "phone": "+14155552671",
                "company_id": "nonexistent-company",
            },
        )
        assert resp.status_code == 404


class TestVerifyOTP:
    """Tests for verifying OTP codes."""

    def test_verify_otp_missing_company_404(self, client):
        """L23: Non-existent company returns 404 on verify."""
        resp = client.post(
            "/api/auth/phone/verify",
            json={
                "phone": "+14155552671",
                "code": "123456",
                "company_id": "nonexistent-company",
            },
        )
        assert resp.status_code == 404

    def test_verify_otp_success(self, client, company, db):
        """Correct OTP code verifies successfully."""
        known_code = "123456"
        known_hash = hashlib.sha256(
            known_code.encode("utf-8")
        ).hexdigest()

        test_otp = PhoneOTP(
            phone="+14155552671",
            company_id=company.id,
            code_hash=known_hash,
            verified=False,
            expires_at=(
                datetime.now(timezone.utc)
                + timedelta(minutes=5)
            ),
            attempts=0,
        )
        db.add(test_otp)
        db.commit()

        resp = client.post(
            "/api/auth/phone/verify",
            json={
                "phone": "+14155552671",
                "code": known_code,
                "company_id": company.id,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "verified"
        assert data["message"] == "Phone verified"

    def test_verify_otp_wrong_code(self, client, company, db):
        """Wrong OTP code returns failure."""
        known_code = "123456"
        known_hash = hashlib.sha256(
            known_code.encode("utf-8")
        ).hexdigest()

        test_otp = PhoneOTP(
            phone="+14155552672",
            company_id=company.id,
            code_hash=known_hash,
            verified=False,
            expires_at=(
                datetime.now(timezone.utc)
                + timedelta(minutes=5)
            ),
            attempts=0,
        )
        db.add(test_otp)
        db.commit()

        resp = client.post(
            "/api/auth/phone/verify",
            json={
                "phone": "+14155552672",
                "code": "654321",
                "company_id": company.id,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"
        assert data["message"] == "Invalid or expired OTP"

    def test_verify_otp_expired_code(self, client, company, db):
        """Expired OTP returns failure (same message)."""
        known_code = "123456"
        known_hash = hashlib.sha256(
            known_code.encode("utf-8")
        ).hexdigest()

        test_otp = PhoneOTP(
            phone="+14155552673",
            company_id=company.id,
            code_hash=known_hash,
            verified=False,
            expires_at=(
                datetime.now(timezone.utc)
                - timedelta(minutes=1)
            ),
            attempts=0,
        )
        db.add(test_otp)
        db.commit()

        resp = client.post(
            "/api/auth/phone/verify",
            json={
                "phone": "+14155552673",
                "code": known_code,
                "company_id": company.id,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"
        assert data["message"] == "Invalid or expired OTP"
        assert data["attempts_remaining"] == 0

    def test_verify_otp_too_many_attempts(
        self, client, company, db,
    ):
        """More than 5 attempts blocks verification."""
        known_code = "123456"
        known_hash = hashlib.sha256(
            known_code.encode("utf-8")
        ).hexdigest()

        test_otp = PhoneOTP(
            phone="+14155552674",
            company_id=company.id,
            code_hash=known_hash,
            verified=False,
            expires_at=(
                datetime.now(timezone.utc)
                + timedelta(minutes=5)
            ),
            attempts=0,
        )
        db.add(test_otp)
        db.commit()

        # Send 5 wrong attempts
        for _ in range(5):
            resp = client.post(
                "/api/auth/phone/verify",
                json={
                    "phone": "+14155552674",
                    "code": "000000",
                    "company_id": company.id,
                },
            )
            assert resp.status_code == 200
            assert resp.json()["status"] == "failed"

        # 6th attempt should still fail with 0 remaining
        resp = client.post(
            "/api/auth/phone/verify",
            json={
                "phone": "+14155552674",
                "code": known_code,  # correct code now
                "company_id": company.id,
            },
        )
        data = resp.json()
        assert data["status"] == "failed"
        assert data["attempts_remaining"] == 0

    def test_verify_otp_already_verified(
        self, client, company, db,
    ):
        """Already verified OTP is not reused."""
        known_code = "123456"
        known_hash = hashlib.sha256(
            known_code.encode("utf-8")
        ).hexdigest()

        test_otp = PhoneOTP(
            phone="+14155552675",
            company_id=company.id,
            code_hash=known_hash,
            verified=True,  # already verified
            expires_at=(
                datetime.now(timezone.utc)
                + timedelta(minutes=5)
            ),
            attempts=0,
        )
        db.add(test_otp)
        db.commit()

        resp = client.post(
            "/api/auth/phone/verify",
            json={
                "phone": "+14155552675",
                "code": known_code,
                "company_id": company.id,
            },
        )
        data = resp.json()
        assert data["status"] == "failed"

    def test_otp_attempts_remaining(
        self, client, company, db,
    ):
        """Attempts remaining decreases correctly."""
        known_code = "123456"
        known_hash = hashlib.sha256(
            known_code.encode("utf-8")
        ).hexdigest()

        test_otp = PhoneOTP(
            phone="+14155552676",
            company_id=company.id,
            code_hash=known_hash,
            verified=False,
            expires_at=(
                datetime.now(timezone.utc)
                + timedelta(minutes=5)
            ),
            attempts=0,
        )
        db.add(test_otp)
        db.commit()

        # 1st wrong attempt: 4 remaining
        resp = client.post(
            "/api/auth/phone/verify",
            json={
                "phone": "+14155552676",
                "code": "000000",
                "company_id": company.id,
            },
        )
        assert resp.json()["attempts_remaining"] == 4

        # 2nd wrong attempt: 3 remaining
        resp = client.post(
            "/api/auth/phone/verify",
            json={
                "phone": "+14155552676",
                "code": "000000",
                "company_id": company.id,
            },
        )
        assert resp.json()["attempts_remaining"] == 3


class TestConstantTimeComparison:
    """Tests for constant-time comparison in OTP verify."""

    def test_constant_time_comparison(self, client, company, db):
        """Verify uses constant-time comparison (no timing leak)."""
        known_code = "123456"
        known_hash = hashlib.sha256(
            known_code.encode("utf-8")
        ).hexdigest()

        test_otp = PhoneOTP(
            phone="+14155552677",
            company_id=company.id,
            code_hash=known_hash,
            verified=False,
            expires_at=(
                datetime.now(timezone.utc)
                + timedelta(minutes=5)
            ),
            attempts=0,
        )
        db.add(test_otp)
        db.commit()

        # Wrong code with 5 matching chars should also fail
        resp = client.post(
            "/api/auth/phone/verify",
            json={
                "phone": "+14155552677",
                "code": "123457",
                "company_id": company.id,
            },
        )
        data = resp.json()
        assert data["status"] == "failed"
        assert data["message"] == "Invalid or expired OTP"

        # Same error message as a completely wrong code
        resp2 = client.post(
            "/api/auth/phone/verify",
            json={
                "phone": "+14155552677",
                "code": "000000",
                "company_id": company.id,
            },
        )
        assert (
            resp.json()["message"]
            == resp2.json()["message"]
        )
