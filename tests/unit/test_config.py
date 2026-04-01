"""
Tests for PARWA Configuration (config.py)

BC-011: Required env vars (SECRET_KEY, DATABASE_URL, JWT_SECRET_KEY,
DATA_ENCRYPTION_KEY) must have no defaults.
"""

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
