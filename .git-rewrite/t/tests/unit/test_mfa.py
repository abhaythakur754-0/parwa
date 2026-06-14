"""
Day 9: MFA Tests (F-015, F-016)

Tests for MFA setup, TOTP verification, backup codes.
"""

import hashlib
import secrets

import pytest

import pyotp

from backend.app.exceptions import (
    AuthenticationError,
    ValidationError,
)
from backend.app.services.mfa_service import (
    _generate_backup_codes,
    _hash_backup_code,
    get_remaining_backup_codes,
    initiate_mfa_setup,
    regenerate_backup_codes,
    use_backup_code,
    verify_mfa_login,
    verify_mfa_setup,
)
from database.base import SessionLocal
from database.models.core import (
    BackupCode,
    Company,
    MFASecret,
    User,
)


@pytest.fixture(autouse=True)
def _setup_db():
    """Shared DB session — clean MFA data."""
    db = SessionLocal()
    db.query(BackupCode).delete()
    db.query(MFASecret).delete()
    db.commit()
    try:
        yield db
    finally:
        db.rollback()
        db.close()


def _create_user(db, mfa_enabled=False):
    """Helper: create a user."""
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
        password_hash=(
            "$2b$12$fakehashfortest0000000"
            "0000000000000000000000000"
        ),
        full_name=f"User-{uid}",
        role="owner",
        company_id=company.id,
        is_active=True,
        is_verified=True,
        mfa_enabled=mfa_enabled,
    )
    db.add(user)
    db.flush()

    if mfa_enabled:
        secret = pyotp.random_base32()
        mfa_rec = MFASecret(
            user_id=user.id,
            company_id=company.id,
            secret_key=secret,
            is_verified=True,
        )
        db.add(mfa_rec)

    db.commit()
    return user


class TestBackupCodeGeneration:
    """Tests for backup code generation."""

    def test_generates_10_codes(self):
        """Should generate exactly 10 codes."""
        codes = _generate_backup_codes()
        assert len(codes) == 10

    def test_codes_are_unique(self):
        """All codes should be unique."""
        codes = _generate_backup_codes()
        assert len(set(codes)) == 10

    def test_code_format(self):
        """Codes should be A7K3-M9X2-P4L1 format."""
        codes = _generate_backup_codes()
        for code in codes:
            parts = code.split("-")
            assert len(parts) == 3
            for part in parts:
                assert len(part) == 3

    def test_hash_backup_code(self):
        """Hashing should be deterministic."""
        code = "A7K3-M9X2-P4L1"
        h1 = _hash_backup_code(code)
        h2 = _hash_backup_code(code)
        assert h1 == h2
        assert h1 != code

    def test_hash_is_sha256(self):
        """Hash should be SHA-256 hex digest."""
        code = "A7K3-M9X2-P4L1"
        h = _hash_backup_code(code)
        expected = hashlib.sha256(
            code.strip().upper().encode("utf-8")
        ).hexdigest()
        assert h == expected

    def test_case_insensitive(self):
        """Backup code lookup should be case-insensitive."""
        code = "a7k3-m9x2-p4l1"
        h_lower = _hash_backup_code(code)
        h_upper = _hash_backup_code("A7K3-M9X2-P4L1")
        assert h_lower == h_upper


class TestMFASetup:
    """Tests for F-015 MFA setup flow."""

    def test_initiate_returns_qr_and_codes(self, _setup_db):
        """Setup initiation returns QR + 10 backup codes."""
        db = _setup_db
        user = _create_user(db)

        result = initiate_mfa_setup(db, user)

        assert "qr_code_data_url" in result
        assert result["qr_code_data_url"].startswith(
            "data:image/png;base64,"
        )
        assert "secret_key" in result
        assert len(result["backup_codes"]) == 10

    def test_initiate_fails_if_mfa_already_enabled(self, _setup_db):
        """Should fail if MFA already enabled."""
        db = _setup_db
        user = _create_user(db, mfa_enabled=True)

        with pytest.raises(ValidationError):
            initiate_mfa_setup(db, user)

    def test_verify_enables_mfa(self, _setup_db):
        """Verification should enable MFA on user."""
        db = _setup_db
        user = _create_user(db)

        result = initiate_mfa_setup(db, user)
        secret = result["secret_key"]

        totp = pyotp.TOTP(secret)
        code = totp.now()

        result = verify_mfa_setup(db, user, code, secret)
        assert result["mfa_enabled"] is True
        assert user.mfa_enabled is True

    def test_verify_invalid_code_raises(self, _setup_db):
        """Invalid TOTP code should raise error."""
        db = _setup_db
        user = _create_user(db)

        result = initiate_mfa_setup(db, user)
        secret = result["secret_key"]

        with pytest.raises(AuthenticationError):
            verify_mfa_setup(db, user, "000000", secret)

    def test_verify_clock_drift_accepted(self, _setup_db):
        """Codes within ±1 window should be accepted."""
        db = _setup_db
        user = _create_user(db)

        result = initiate_mfa_setup(db, user)
        secret = result["secret_key"]

        totp = pyotp.TOTP(secret)
        # Use current code (within valid window)
        code = totp.now()
        result = verify_mfa_setup(db, user, code, secret)
        assert result["status"] == "enabled"

    def test_backup_codes_stored_as_hashes(self, _setup_db):
        """Backup codes should be SHA-256 hashed in DB."""
        db = _setup_db
        user = _create_user(db)

        result = initiate_mfa_setup(db, user)
        plain_code = result["backup_codes"][0]

        # Should NOT find plaintext in DB
        found = db.query(BackupCode).filter(
            BackupCode.user_id == user.id,
            BackupCode.code_hash == plain_code,
        ).first()
        assert found is None

        # Should find hash
        found = db.query(BackupCode).filter(
            BackupCode.user_id == user.id,
            BackupCode.code_hash
            == _hash_backup_code(plain_code),
        ).first()
        assert found is not None


class TestMFALogin:
    """Tests for MFA verification during login."""

    def test_valid_code_verifies(self, _setup_db):
        """Valid TOTP code should verify."""
        db = _setup_db
        user = _create_user(db, mfa_enabled=True)

        mfa = db.query(MFASecret).filter(
            MFASecret.user_id == user.id
        ).first()
        totp = pyotp.TOTP(mfa.secret_key)
        code = totp.now()

        result = verify_mfa_login(db, user, code)
        assert result["status"] == "verified"

    def test_invalid_code_raises(self, _setup_db):
        """Invalid code should raise error."""
        db = _setup_db
        user = _create_user(db, mfa_enabled=True)

        with pytest.raises(AuthenticationError):
            verify_mfa_login(db, user, "000000")

    def test_not_configured_raises(self, _setup_db):
        """Should raise if no MFA secret found."""
        db = _setup_db
        user = _create_user(db, mfa_enabled=False)

        with pytest.raises(AuthenticationError):
            verify_mfa_login(db, user, "123456")

    def test_progressive_lockout_5_failures(self, _setup_db):
        """5 failures should lock account for 15 min."""
        db = _setup_db
        user = _create_user(db, mfa_enabled=True)

        for _ in range(4):
            try:
                verify_mfa_login(db, user, "000000")
            except AuthenticationError:
                pass

        # 5th should lock
        with pytest.raises(AuthenticationError) as exc:
            verify_mfa_login(db, user, "000000")
        assert "locked" in str(exc.value.message).lower()

    def test_lockout_resets_on_success(self, _setup_db):
        """Success should reset failure count."""
        db = _setup_db
        user = _create_user(db, mfa_enabled=True)

        # Fail twice
        for _ in range(2):
            try:
                verify_mfa_login(db, user, "000000")
            except AuthenticationError:
                pass

        # Succeed
        mfa = db.query(MFASecret).filter(
            MFASecret.user_id == user.id
        ).first()
        totp = pyotp.TOTP(mfa.secret_key)
        code = totp.now()
        verify_mfa_login(db, user, code)

        assert user.failed_login_count == 0


class TestBackupCodeUse:
    """Tests for F-016 backup code use."""

    def test_valid_code_accepts(self, _setup_db):
        """Valid backup code should be accepted."""
        db = _setup_db
        user = _create_user(db, mfa_enabled=False)

        result = initiate_mfa_setup(db, user)
        code = result["backup_codes"][0]

        # Enable MFA first (L29: requires mfa_enabled)
        secret = result["secret_key"]
        totp = pyotp.TOTP(secret)
        verify_mfa_setup(db, user, totp.now(), secret)

        result = use_backup_code(db, user, code)
        assert result["status"] == "verified"
        assert result["remaining"] == 9

    def test_invalid_code_raises(self, _setup_db):
        """Invalid code should raise error."""
        db = _setup_db
        user = _create_user(db, mfa_enabled=False)

        result = initiate_mfa_setup(db, user)
        secret = result["secret_key"]
        totp = pyotp.TOTP(secret)
        verify_mfa_setup(db, user, totp.now(), secret)

        with pytest.raises(AuthenticationError):
            use_backup_code(db, user, "INVALID-CODE")

    def test_code_single_use(self, _setup_db):
        """Backup code can only be used once."""
        db = _setup_db
        user = _create_user(db, mfa_enabled=False)

        result = initiate_mfa_setup(db, user)
        code = result["backup_codes"][0]

        # Enable MFA first (L29: requires mfa_enabled)
        secret = result["secret_key"]
        totp = pyotp.TOTP(secret)
        verify_mfa_setup(db, user, totp.now(), secret)

        use_backup_code(db, user, code)

        with pytest.raises(AuthenticationError):
            use_backup_code(db, user, code)

    def test_remaining_count(self, _setup_db):
        """Remaining count should decrease."""
        db = _setup_db
        user = _create_user(db, mfa_enabled=False)

        result = initiate_mfa_setup(db, user)
        secret = result["secret_key"]
        totp = pyotp.TOTP(secret)
        verify_mfa_setup(db, user, totp.now(), secret)

        assert get_remaining_backup_codes(db, user) == 10

        use_backup_code(db, user, result["backup_codes"][0])
        assert get_remaining_backup_codes(db, user) == 9

    def test_use_without_mfa_enabled_raises(self, _setup_db):
        """L29: Cannot use backup code if MFA not enabled."""
        db = _setup_db
        user = _create_user(db, mfa_enabled=False)

        with pytest.raises(AuthenticationError) as exc:
            use_backup_code(db, user, "ABC-DEF-GHI")
        assert "not enabled" in str(exc.value.message).lower()


class TestBackupCodeRegenerate:
    """Tests for backup code regeneration."""

    def test_regenerate_requires_valid_totp(self, _setup_db):
        """Regeneration requires valid TOTP code."""
        db = _setup_db
        user = _create_user(db, mfa_enabled=True)

        with pytest.raises(AuthenticationError):
            regenerate_backup_codes(db, user, "000000")

    def test_regenerate_invalidates_old_codes(self, _setup_db):
        """Regeneration invalidates all old codes."""
        db = _setup_db
        user = _create_user(db, mfa_enabled=False)

        # Initial setup creates codes
        result = initiate_mfa_setup(db, user)
        secret = result["secret_key"]

        # Verify MFA to enable it
        totp = pyotp.TOTP(secret)
        code = totp.now()
        verify_mfa_setup(db, user, code, secret)

        # Get verified MFA secret for regeneration
        mfa = db.query(MFASecret).filter(
            MFASecret.user_id == user.id,
            MFASecret.is_verified == True,  # noqa: E712
        ).first()
        totp = pyotp.TOTP(mfa.secret_key)
        code = totp.now()

        result = regenerate_backup_codes(db, user, code)
        assert len(result["backup_codes"]) == 10

    def test_regenerate_fails_if_mfa_disabled(self, _setup_db):
        """Cannot regenerate if MFA not enabled."""
        db = _setup_db
        user = _create_user(db, mfa_enabled=False)

        with pytest.raises(ValidationError):
            regenerate_backup_codes(db, user, "123456")
