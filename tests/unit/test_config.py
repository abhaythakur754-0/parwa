"""
Unit tests for the config module.
"""
import pytest
import os
from pydantic import ValidationError
from shared.core_functions.config import Settings, get_settings


def test_config_loads_defaults(monkeypatch):
    """Test that default values are loaded correctly when env vars are present."""
    # Clear the cache to ensure fresh settings
    get_settings.cache_clear()
    
    # Set required environment variables for this test
    env_vars = {
        "ENVIRONMENT": "development",
        "SECRET_KEY": "test-secret-key",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "GOOGLE_AI_API_KEY": "test_google_api_key_for_testing",
        "STRIPE_SECRET_KEY": "sk_test_123",
        "STRIPE_PUBLISHABLE_KEY": "pk_test_123",
        "FROM_EMAIL": "test@test.com",
        "FEATURE_FLAGS_PATH": "./flags",
        "DATA_ENCRYPTION_KEY": "12345678901234567890123456789012",
    }

    for k, v in env_vars.items():
        monkeypatch.setenv(k, v)

    settings = Settings()
    assert settings.environment == "development"
    # debug defaults to True in the Settings class
    assert settings.debug is True


def test_settings_uses_env_vars():
    """Test that Settings uses environment variables from conftest."""
    # This test uses the env vars set by conftest.py
    get_settings.cache_clear()
    settings = get_settings()
    
    # These are set by conftest.py
    assert settings.environment == "test"
    assert settings.secret_key.get_secret_value() == "test_secret_key_for_unit_tests_not_for_production"
    assert "test_db" in settings.database_url


def test_production_validation_blocks_defaults(monkeypatch):
    """Test that production validation rejects default secret keys."""
    env_vars = {
        "ENVIRONMENT": "production",
        "SECRET_KEY": "placeholder-production-key",  # Contains "placeholder" - should fail
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "GOOGLE_AI_API_KEY": "test_google_key",
        "STRIPE_SECRET_KEY": "sk_test_123",
        "STRIPE_PUBLISHABLE_KEY": "pk_test_123",
        "FROM_EMAIL": "test@test.com",
        "FEATURE_FLAGS_PATH": "./flags",
        "DATA_ENCRYPTION_KEY": "placeholder-key",  # Contains "placeholder" - should fail
    }

    for k, v in env_vars.items():
        monkeypatch.setenv(k, v)

    # Need to clear the cache so get_settings runs fresh
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="Critical security keys missing or set to default"):
        get_settings()


def test_production_validation_passes(monkeypatch):
    """Test that production validation passes when secure keys are provided."""
    env_vars = {
        "ENVIRONMENT": "production",
        "SECRET_KEY": "secure-secret-key-that-is-very-long-and-secure-for-real",
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "GOOGLE_AI_API_KEY": "test_google_api_key_for_production",
        "CEREBRAS_API_KEY": "test_cerebras_api_key_for_production",
        "GROQ_API_KEY": "test_groq_api_key_for_production",
        "STRIPE_SECRET_KEY": "sk_test_123",
        "STRIPE_PUBLISHABLE_KEY": "pk_test_123",
        "FROM_EMAIL": "test@test.com",
        "FEATURE_FLAGS_PATH": "./flags",
        "DATA_ENCRYPTION_KEY": "secure-encryption-key-for-data-32chars-safe",
    }

    for k, v in env_vars.items():
        monkeypatch.setenv(k, v)

    get_settings.cache_clear()

    settings = get_settings()
    assert settings.environment == "production"


def test_settings_has_sentry_dsn(monkeypatch):
    """Test that sentry_dsn is available in Settings."""
    monkeypatch.setenv("SENTRY_DSN", "https://dsn@sentry.io/1")
    
    settings = Settings()
    assert settings.sentry_dsn == "https://dsn@sentry.io/1"


def test_llm_config_google(monkeypatch):
    """Test LLM config retrieval for Google provider."""
    monkeypatch.setenv("GOOGLE_AI_API_KEY", "test_google_key")
    
    settings = Settings()
    config = settings.get_llm_config("google")
    
    assert config["api_key"] == "test_google_key"
    assert "gemini" in config["models"]["heavy"]


def test_llm_config_cerebras():
    """Test LLM config retrieval for Cerebras provider."""
    settings = Settings(
        environment="test",
        secret_key="test",
        **{"CEREBRAS_API_KEY": "test_cerebras_key"}
    )
    config = settings.get_llm_config("cerebras")
    
    assert config["api_key"] == "test_cerebras_key"
    assert "llama" in config["models"]["heavy"]


def test_llm_config_groq():
    """Test LLM config retrieval for Groq provider."""
    settings = Settings(
        environment="test",
        secret_key="test",
        **{"GROQ_API_KEY": "test_groq_key"}
    )
    config = settings.get_llm_config("groq")
    
    assert config["api_key"] == "test_groq_key"
    assert "llama" in config["models"]["heavy"]


def test_is_production_property():
    """Test is_production property - uses env var for environment."""
    # Settings reads from env vars, so we need to set ENVIRONMENT
    settings = Settings()  # Uses test environment from conftest
    assert settings.is_production is False  # "test" != "production"


def test_async_database_url_property():
    """Test async_database_url property - uses env var for database_url."""
    settings = Settings()  # Uses test db from conftest
    # The conftest sets DATABASE_URL to postgresql+asyncpg://
    assert settings.async_database_url.startswith("postgresql+asyncpg://")
    assert "test_db" in settings.async_database_url
