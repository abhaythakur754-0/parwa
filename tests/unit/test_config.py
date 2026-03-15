"""
Unit tests for the config module.
"""
import pytest
from pydantic import ValidationError
from shared.core_functions.config import Settings, get_settings


def test_config_loads_defaults(monkeypatch):
    """Test that default values are loaded correctly when env vars are present."""
    env_vars = {
        "ENVIRONMENT": "development",
        "SECRET_KEY": "test-secret-key",
        "POSTGRES_USER": "parwa",
        "POSTGRES_PASSWORD": "parwa_dev",
        "POSTGRES_DB": "parwa_db",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "JWT_SECRET_KEY": "test-jwt-secret",
        "OPENROUTER_API_KEY": "sk-test",
        "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
        "AI_LIGHT_MODEL": "test/light",
        "AI_MEDIUM_MODEL": "test/medium",
        "AI_HEAVY_MODEL": "test/heavy",
        "AI_FAILOVER_MODEL": "test/failover",
        "STRIPE_SECRET_KEY": "sk_test_123",
        "STRIPE_PUBLISHABLE_KEY": "pk_test_123",
        "STRIPE_WEBHOOK_SECRET": "whsec_123",
        "TWILIO_ACCOUNT_SID": "AC123",
        "TWILIO_AUTH_TOKEN": "token",
        "TWILIO_PHONE_NUMBER": "+123456",
        "TWILIO_VOICE_WEBHOOK_URL": "https://test.com",
        "SHOPIFY_API_KEY": "key",
        "SHOPIFY_API_SECRET": "secret",
        "SHOPIFY_WEBHOOK_SECRET": "webhook",
        "MCP_SERVER_URL": "http://localhost:8001",
        "MCP_AUTH_TOKEN": "token",
        "QDRANT_URL": "http://localhost:6333",
        "QDRANT_API_KEY": "key",
        "SENDGRID_API_KEY": "SG.key",
        "FROM_EMAIL": "test@test.com",
        "SENTRY_DSN": "https://dsn@sentry.io/1",
        "GRAFANA_API_KEY": "key",
        "NEXT_PUBLIC_API_URL": "http://localhost:8000",
        "NEXT_PUBLIC_STRIPE_KEY": "pk_test",
        "FEATURE_FLAGS_PATH": "./flags",
        "MODEL_REGISTRY_PATH": "./models",
        "COLAB_WEBHOOK_URL": "https://webhook.com",
        "DATA_ENCRYPTION_KEY": "key"
    }

    for k, v in env_vars.items():
        monkeypatch.setenv(k, v)

    settings = Settings(_env_file=None)
    assert settings.environment == "development"
    assert settings.debug is False
    assert settings.jwt_access_token_expire_minutes == 60


def test_missing_required_env_var(monkeypatch):
    """Test that missing required variables raise a ValidationError."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_production_validation_blocks_defaults(monkeypatch):
    """Test that production validation rejects default 'your-' keys."""
    env_vars = {
        "ENVIRONMENT": "production",
        "SECRET_KEY": "your-super-secret-key-at-least-32-chars",
        "POSTGRES_USER": "parwa",
        "POSTGRES_PASSWORD": "parwa_dev",
        "POSTGRES_DB": "parwa_db",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "JWT_SECRET_KEY": "your-jwt-secret-key-at-least-32-chars",
        "OPENROUTER_API_KEY": "sk-test",
        "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
        "AI_LIGHT_MODEL": "test/light",
        "AI_MEDIUM_MODEL": "test/medium",
        "AI_HEAVY_MODEL": "test/heavy",
        "AI_FAILOVER_MODEL": "test/failover",
        "STRIPE_SECRET_KEY": "sk_test_123",
        "STRIPE_PUBLISHABLE_KEY": "pk_test_123",
        "STRIPE_WEBHOOK_SECRET": "whsec_123",
        "TWILIO_ACCOUNT_SID": "AC123",
        "TWILIO_AUTH_TOKEN": "token",
        "TWILIO_PHONE_NUMBER": "+123456",
        "TWILIO_VOICE_WEBHOOK_URL": "https://test.com",
        "SHOPIFY_API_KEY": "key",
        "SHOPIFY_API_SECRET": "secret",
        "SHOPIFY_WEBHOOK_SECRET": "webhook",
        "MCP_SERVER_URL": "http://localhost:8001",
        "MCP_AUTH_TOKEN": "token",
        "QDRANT_URL": "http://localhost:6333",
        "QDRANT_API_KEY": "key",
        "SENDGRID_API_KEY": "SG.key",
        "FROM_EMAIL": "test@test.com",
        "SENTRY_DSN": "https://dsn@sentry.io/1",
        "GRAFANA_API_KEY": "key",
        "NEXT_PUBLIC_API_URL": "http://localhost:8000",
        "NEXT_PUBLIC_STRIPE_KEY": "pk_test",
        "FEATURE_FLAGS_PATH": "./flags",
        "MODEL_REGISTRY_PATH": "./models",
        "COLAB_WEBHOOK_URL": "https://webhook.com",
        "DATA_ENCRYPTION_KEY": "your-32-byte-encryption-key"
    }

    for k, v in env_vars.items():
        monkeypatch.setenv(k, v)

    # Need to clear the cache so get_settings runs fresh
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="Critical security keys missing or set to default in production."):
        get_settings()


def test_production_validation_passes(monkeypatch):
    """Test that production validation passes when secure keys are provided."""
    env_vars = {
        "ENVIRONMENT": "production",
        "SECRET_KEY": "secure-secret-key-that-is-very-long",
        "POSTGRES_USER": "parwa",
        "POSTGRES_PASSWORD": "parwa_dev",
        "POSTGRES_DB": "parwa_db",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "JWT_SECRET_KEY": "secure-jwt-secret-key",
        "OPENROUTER_API_KEY": "sk-test",
        "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1",
        "AI_LIGHT_MODEL": "test/light",
        "AI_MEDIUM_MODEL": "test/medium",
        "AI_HEAVY_MODEL": "test/heavy",
        "AI_FAILOVER_MODEL": "test/failover",
        "STRIPE_SECRET_KEY": "sk_test_123",
        "STRIPE_PUBLISHABLE_KEY": "pk_test_123",
        "STRIPE_WEBHOOK_SECRET": "whsec_123",
        "TWILIO_ACCOUNT_SID": "AC123",
        "TWILIO_AUTH_TOKEN": "token",
        "TWILIO_PHONE_NUMBER": "+123456",
        "TWILIO_VOICE_WEBHOOK_URL": "https://test.com",
        "SHOPIFY_API_KEY": "key",
        "SHOPIFY_API_SECRET": "secret",
        "SHOPIFY_WEBHOOK_SECRET": "webhook",
        "MCP_SERVER_URL": "http://localhost:8001",
        "MCP_AUTH_TOKEN": "token",
        "QDRANT_URL": "http://localhost:6333",
        "QDRANT_API_KEY": "key",
        "SENDGRID_API_KEY": "SG.key",
        "FROM_EMAIL": "test@test.com",
        "SENTRY_DSN": "https://dsn@sentry.io/1",
        "GRAFANA_API_KEY": "key",
        "NEXT_PUBLIC_API_URL": "http://localhost:8000",
        "NEXT_PUBLIC_STRIPE_KEY": "pk_test",
        "FEATURE_FLAGS_PATH": "./flags",
        "MODEL_REGISTRY_PATH": "./models",
        "COLAB_WEBHOOK_URL": "https://webhook.com",
        "DATA_ENCRYPTION_KEY": "secure-encryption-key-for-data"
    }

    for k, v in env_vars.items():
        monkeypatch.setenv(k, v)

    get_settings.cache_clear()

    settings = get_settings()
    assert settings.environment == "production"
