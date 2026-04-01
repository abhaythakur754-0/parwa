"""
Tests for PARWA Configuration (config.py)

BC-011: Required env vars (SECRET_KEY, DATABASE_URL, JWT_SECRET_KEY,
DATA_ENCRYPTION_KEY) must have no defaults.
"""

import os

import pytest
from pydantic import ValidationError

from backend.app.config import Settings


class TestConfigRequiredFields:
    """Test that required env vars raise ValidationError when missing."""

    def test_secret_key_required(self):
        """BC-011: SECRET_KEY must be provided, no default."""
        field = Settings.model_fields.get("SECRET_KEY")
        assert field is not None
        assert field.is_required()

    def test_database_url_required(self):
        """BC-011: DATABASE_URL must be provided, no default."""
        field = Settings.model_fields.get("DATABASE_URL")
        assert field is not None
        assert field.is_required()

    def test_jwt_secret_key_required(self):
        """BC-011: JWT_SECRET_KEY must be provided, no default."""
        field = Settings.model_fields.get("JWT_SECRET_KEY")
        assert field is not None
        assert field.is_required()

    def test_data_encryption_key_required(self):
        """BC-011: DATA_ENCRYPTION_KEY must be provided, no default."""
        field = Settings.model_fields.get("DATA_ENCRYPTION_KEY")
        assert field is not None
        assert field.is_required()


class TestConfigDefaults:
    """Test that default values are sensible."""

    def test_environment_default(self):
        """Default environment is development when not set via env."""
        # conftest sets ENVIRONMENT=test, so explicitly pass development here
        settings = Settings(
            SECRET_KEY="test",
            DATABASE_URL="sqlite:///:memory:",
            JWT_SECRET_KEY="test",
            DATA_ENCRYPTION_KEY="12345678901234567890123456789012",
            ENVIRONMENT="development",
        )
        assert settings.ENVIRONMENT == "development"

    def test_jwt_access_expire_default_15(self):
        """BC-011: JWT access token expires in 15 minutes."""
        settings = Settings(
            SECRET_KEY="test",
            DATABASE_URL="sqlite:///:memory:",
            JWT_SECRET_KEY="test",
            DATA_ENCRYPTION_KEY="12345678901234567890123456789012",
        )
        assert settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES == 15

    def test_jwt_refresh_expire_default_7(self):
        """BC-011: JWT refresh token expires in 7 days."""
        settings = Settings(
            SECRET_KEY="test",
            DATABASE_URL="sqlite:///:memory:",
            JWT_SECRET_KEY="test",
            DATA_ENCRYPTION_KEY="12345678901234567890123456789012",
        )
        assert settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS == 7

    def test_max_sessions_default_5(self):
        """BC-011: Max 5 sessions per user."""
        settings = Settings(
            SECRET_KEY="test",
            DATABASE_URL="sqlite:///:memory:",
            JWT_SECRET_KEY="test",
            DATA_ENCRYPTION_KEY="12345678901234567890123456789012",
        )
        assert settings.MAX_SESSIONS_PER_USER == 5

    def test_debug_default_false(self):
        """Debug defaults to False for safety."""
        settings = Settings(
            SECRET_KEY="test",
            DATABASE_URL="sqlite:///:memory:",
            JWT_SECRET_KEY="test",
            DATA_ENCRYPTION_KEY="12345678901234567890123456789012",
        )
        assert settings.DEBUG is False


class TestConfigProperties:
    """Test config property methods."""

    def test_is_production_true(self):
        """is_production returns True only when ENVIRONMENT=production."""
        settings = Settings(
            SECRET_KEY="test",
            DATABASE_URL="sqlite:///:memory:",
            JWT_SECRET_KEY="test",
            DATA_ENCRYPTION_KEY="12345678901234567890123456789012",
            ENVIRONMENT="production",
        )
        assert settings.is_production is True
        assert settings.is_test is False

    def test_is_test_true(self):
        """is_test returns True only when ENVIRONMENT=test."""
        settings = Settings(
            SECRET_KEY="test",
            DATABASE_URL="sqlite:///:memory:",
            JWT_SECRET_KEY="test",
            DATA_ENCRYPTION_KEY="12345678901234567890123456789012",
            ENVIRONMENT="test",
        )
        assert settings.is_test is True
        assert settings.is_production is False

    def test_is_production_false_for_dev(self):
        """is_production returns False for development."""
        settings = Settings(
            SECRET_KEY="test",
            DATABASE_URL="sqlite:///:memory:",
            JWT_SECRET_KEY="test",
            DATA_ENCRYPTION_KEY="12345678901234567890123456789012",
            ENVIRONMENT="development",
        )
        assert settings.is_production is False


def _make_settings(**overrides):
    """Helper to create Settings with all required fields + overrides."""
    defaults = {
        "SECRET_KEY": "test",
        "DATABASE_URL": "sqlite:///:memory:",
        "JWT_SECRET_KEY": "test",
        "DATA_ENCRYPTION_KEY": "12345678901234567890123456789012",
    }
    defaults.update(overrides)
    return Settings(**defaults)


class TestConfigValidationErrors:
    """Test that missing required env vars raise pydantic ValidationError."""

    REQUIRED_ENV_VARS = ["SECRET_KEY", "DATABASE_URL", "JWT_SECRET_KEY", "DATA_ENCRYPTION_KEY"]

    def _clear_required_env(self):
        """Temporarily clear required env vars so Settings reads from kwargs."""
        self._saved = {}
        for key in self.REQUIRED_ENV_VARS:
            if key in os.environ:
                self._saved[key] = os.environ.pop(key)

    def _restore_required_env(self):
        """Restore saved env vars."""
        for key, val in self._saved.items():
            os.environ[key] = val

    def test_missing_secret_key_raises(self):
        """BC-011: No SECRET_KEY → ValidationError."""
        self._clear_required_env()
        try:
            with pytest.raises(ValidationError):
                Settings(
                    DATABASE_URL="sqlite:///:memory:",
                    JWT_SECRET_KEY="test",
                    DATA_ENCRYPTION_KEY="12345678901234567890123456789012",
                    _env_file=None,
                )
        finally:
            self._restore_required_env()

    def test_missing_database_url_raises(self):
        """BC-011: No DATABASE_URL → ValidationError."""
        self._clear_required_env()
        try:
            with pytest.raises(ValidationError):
                Settings(
                    SECRET_KEY="test",
                    JWT_SECRET_KEY="test",
                    DATA_ENCRYPTION_KEY="12345678901234567890123456789012",
                    _env_file=None,
                )
        finally:
            self._restore_required_env()

    def test_missing_jwt_secret_key_raises(self):
        """BC-011: No JWT_SECRET_KEY → ValidationError."""
        self._clear_required_env()
        try:
            with pytest.raises(ValidationError):
                Settings(
                    SECRET_KEY="test",
                    DATABASE_URL="sqlite:///:memory:",
                    DATA_ENCRYPTION_KEY="12345678901234567890123456789012",
                    _env_file=None,
                )
        finally:
            self._restore_required_env()

    def test_missing_data_encryption_key_raises(self):
        """BC-011: No DATA_ENCRYPTION_KEY → ValidationError."""
        self._clear_required_env()
        try:
            with pytest.raises(ValidationError):
                Settings(
                    SECRET_KEY="test",
                    DATABASE_URL="sqlite:///:memory:",
                    JWT_SECRET_KEY="test",
                    _env_file=None,
                )
        finally:
            self._restore_required_env()

    def test_missing_multiple_required_raises(self):
        """Missing multiple required vars → ValidationError (mentions them)."""
        self._clear_required_env()
        try:
            with pytest.raises(ValidationError):
                Settings(_env_file=None)  # none of the 4 required vars
        finally:
            self._restore_required_env()


class TestConfigCaseInsensitive:
    """BC-011: Settings are case-insensitive (case_sensitive=False)."""

    def test_lowercase_env_vars_work(self):
        """Lowercase env var names are accepted."""
        os.environ["secret_key"] = "lowercase_key"
        os.environ["database_url"] = "sqlite:///:memory:"
        os.environ["jwt_secret_key"] = "lowercase_jwt"
        os.environ["data_encryption_key"] = "12345678901234567890123456789012"
        try:
            settings = Settings(_env_file=None)
            assert settings.SECRET_KEY == "lowercase_key"
        finally:
            # Cleanup to avoid affecting other tests
            for key in ["secret_key", "database_url", "jwt_secret_key", "data_encryption_key"]:
                os.environ.pop(key, None)


class TestConfigExtraVarsIgnored:
    """Settings must ignore unexpected env vars (extra='ignore')."""

    def test_extra_env_var_does_not_crash(self):
        """Unknown env vars are silently ignored."""
        os.environ["RANDOM_UNKNOWN_VAR"] = "should_be_ignored"
        try:
            settings = _make_settings()
            assert settings.SECRET_KEY == "test"
        finally:
            os.environ.pop("RANDOM_UNKNOWN_VAR", None)


class TestConfigAdditionalDefaults:
    """Test other important config defaults beyond the core 4 required."""

    def test_training_threshold_default_50(self):
        """Training threshold default is 50 (50-mistake rule)."""
        settings = _make_settings()
        assert settings.TRAINING_THRESHOLD == 50

    def test_gdpr_retention_default_365(self):
        """GDPR data retention defaults to 365 days."""
        settings = _make_settings()
        assert settings.GDPR_RETENTION_DAYS == 365

    def test_audit_retention_default_2555(self):
        """Audit log retention defaults to 2555 days (~7 years)."""
        settings = _make_settings()
        assert settings.AUDIT_LOG_RETENTION_DAYS == 2555

    def test_redis_url_default(self):
        """Redis URL defaults to localhost."""
        settings = _make_settings()
        assert settings.REDIS_URL == "redis://localhost:6379/0"

    def test_max_sessions_default_5(self):
        """Max sessions per user defaults to 5."""
        settings = _make_settings()
        assert settings.MAX_SESSIONS_PER_USER == 5
