"""
Configuration manager for PARWA.
Loads environment variables and provides them as typed objects.
Supports multiple LLM providers: Google AI, Cerebras, Groq.
"""
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr


class Settings(BaseSettings):
    """
    Main settings class loading configuration from .env.
    Validates required fields strictly, particularly for production environments.
    """
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    # ─────────────────────────────────────────────────────────────
    # APPLICATION
    # ─────────────────────────────────────────────────────────────
    environment: str = Field(default="development", alias="ENVIRONMENT")
    secret_key: SecretStr = Field(default="dev_secret_key", alias="SECRET_KEY")
    debug: bool = Field(default=True, alias="DEBUG")

    # ─────────────────────────────────────────────────────────────
    # DATABASE (Docker/PostgreSQL)
    # ─────────────────────────────────────────────────────────────
    postgres_user: str = Field(default="parwa", alias="POSTGRES_USER")
    postgres_password: str = Field(default="parwa_dev", alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(default="parwa_db", alias="POSTGRES_DB")
    database_url: str = Field(
        default="postgresql://parwa:parwa_dev@localhost:5432/parwa_db",
        alias="DATABASE_URL"
    )
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # ─────────────────────────────────────────────────────────────
    # LLM APIs - Multiple Providers
    # ─────────────────────────────────────────────────────────────
    # Google AI Studio (Primary)
    google_ai_api_key: Optional[SecretStr] = Field(default=None, alias="GOOGLE_AI_API_KEY")

    # Cerebras (Fast Inference)
    cerebras_api_key: Optional[SecretStr] = Field(default=None, alias="CEREBRAS_API_KEY")

    # Groq (Alternative Fast)
    groq_api_key: Optional[SecretStr] = Field(default=None, alias="GROQ_API_KEY")

    # LLM Provider Selection
    llm_primary_provider: str = Field(default="google", alias="LLM_PRIMARY_PROVIDER")
    llm_fallback_provider: str = Field(default="groq", alias="LLM_FALLBACK_PROVIDER")

    # ─────────────────────────────────────────────────────────────
    # PAYMENT (Stripe)
    # ─────────────────────────────────────────────────────────────
    stripe_secret_key: Optional[SecretStr] = Field(default=None, alias="STRIPE_SECRET_KEY")
    stripe_publishable_key: Optional[str] = Field(default=None, alias="STRIPE_PUBLISHABLE_KEY")

    # ─────────────────────────────────────────────────────────────
    # SMS/VOICE (Bird)
    # ─────────────────────────────────────────────────────────────
    bird_api_key: Optional[SecretStr] = Field(default=None, alias="BIRD_API_KEY")
    bird_access_key: Optional[str] = Field(default=None, alias="BIRD_ACCESS_KEY")

    # ─────────────────────────────────────────────────────────────
    # EMAIL (Brevo)
    # ─────────────────────────────────────────────────────────────
    brevo_api_key: Optional[SecretStr] = Field(default=None, alias="BREVO_API_KEY")
    from_email: str = Field(default="noreply@parwa.ai", alias="FROM_EMAIL")

    # ─────────────────────────────────────────────────────────────
    # COMPLIANCE
    # ─────────────────────────────────────────────────────────────
    gdpr_retention_days: int = Field(default=365, alias="GDPR_RETENTION_DAYS")
    audit_log_retention_days: int = Field(default=2555, alias="AUDIT_LOG_RETENTION_DAYS")
    data_encryption_key: SecretStr = Field(
        default="12345678901234567890123456789012",
        alias="DATA_ENCRYPTION_KEY"
    )

    # ─────────────────────────────────────────────────────────────
    # FEATURE FLAGS
    # ─────────────────────────────────────────────────────────────
    feature_flags_path: str = Field(default="feature_flags", alias="FEATURE_FLAGS_PATH")

    # ─────────────────────────────────────────────────────────────
    # AGENT LIGHTNING
    # ─────────────────────────────────────────────────────────────
    training_threshold: int = Field(default=50, alias="TRAINING_THRESHOLD")

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def async_database_url(self) -> str:
        """Get async database URL for SQLAlchemy."""
        url = self.database_url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    def get_llm_config(self, provider: str = None) -> dict:
        """
        Get LLM configuration for specified provider.

        Args:
            provider: "google", "cerebras", "groq", or None (uses primary)

        Returns:
            Dict with api_key, base_url, and models
        """
        provider = provider or self.llm_primary_provider

        configs = {
            "google": {
                "api_key": self.google_ai_api_key.get_secret_value() if self.google_ai_api_key else None,
                "base_url": "https://generativelanguage.googleapis.com/v1beta",
                "models": {
                    "light": "gemma-2-2b-it",
                    "medium": "gemma-2-9b-it",
                    "heavy": "gemini-1.5-flash",
                }
            },
            "cerebras": {
                "api_key": self.cerebras_api_key.get_secret_value() if self.cerebras_api_key else None,
                "base_url": "https://api.cerebras.ai/v1",
                "models": {
                    "light": "llama-3.1-8b",
                    "medium": "llama-3.3-70b",
                    "heavy": "llama-3.3-70b",
                }
            },
            "groq": {
                "api_key": self.groq_api_key.get_secret_value() if self.groq_api_key else None,
                "base_url": "https://api.groq.com/openai/v1",
                "models": {
                    "light": "gemma2-9b-it",
                    "medium": "llama-3.1-8b-instant",
                    "heavy": "llama-3.1-70b-versatile",
                }
            }
        }

        return configs.get(provider, configs["google"])


@lru_cache()
def get_settings() -> Settings:
    """
    Retrieve the cached settings instance.
    Raises ValueError if critical variables are missing in production.
    """
    settings = Settings()
    if settings.is_production:
        _validate_production_settings(settings)
    return settings


def _validate_production_settings(settings: Settings) -> None:
    """Validate that critical secrets are present in production and not defaults."""
    critical_secrets = [
        settings.secret_key,
        settings.data_encryption_key,
    ]
    for secret in critical_secrets:
        if not secret or not secret.get_secret_value() or "placeholder" in secret.get_secret_value():
            raise ValueError("Critical security keys missing or set to default in production.")

    # Validate at least one LLM provider is configured
    if not any([settings.google_ai_api_key, settings.cerebras_api_key, settings.groq_api_key]):
        raise ValueError("At least one LLM API key must be configured.")
