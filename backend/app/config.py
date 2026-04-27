"""
PARWA Application Configuration

Loads all configuration from environment variables using pydantic-settings.
Required variables (no defaults) per BC-011:
  - SECRET_KEY
  - DATABASE_URL
  - JWT_SECRET_KEY
  - DATA_ENCRYPTION_KEY
  - REFRESH_TOKEN_PEPPER (production only)
"""

import logging
import warnings

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("parwa.config")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────
    ENVIRONMENT: str = "development"
    SECRET_KEY: str  # BC-011: required, no default
    DEBUG: bool = False

    # ── Database ─────────────────────────────────────────────────
    DATABASE_URL: str  # BC-011: required, no default
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── JWT (BC-011) ─────────────────────────────────────────────
    JWT_SECRET_KEY: str  # BC-011: required, no default
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    MAX_SESSIONS_PER_USER: int = 5

    # ── Token Security (Bug Fix Day 4) ──────────────────────────
    # Pepper value mixed into refresh token signatures.
    # Production: REQUIRED (no default).
    # Non-production: uses default with a warning.
    REFRESH_TOKEN_PEPPER: str = "CHANGE_ME_IN_PRODUCTION_p3pp3r!"

    # ── AI Providers ─────────────────────────────────────────────
    GOOGLE_AI_API_KEY: str = ""
    CEREBRAS_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    LLM_PRIMARY_PROVIDER: str = "google"
    LLM_FALLBACK_PROVIDER: str = "groq"
    AI_LIGHT_MODEL: str = ""
    AI_MEDIUM_MODEL: str = ""
    AI_HEAVY_MODEL: str = ""
    AI_FAILOVER_MODEL: str = ""

    # ── Email (Brevo) ────────────────────────────────────────────
    BREVO_API_KEY: str = ""
    FROM_EMAIL: str = "noreply@parwa.ai"
    # Comma-separated CIDR ranges for Brevo inbound webhook IP allowlist.
    # Falls back to DEFAULT_BREVO_IPS in hmac_verification.py if empty.
    BREVO_INBOUND_IPS: str = ""

    # ── SMS/Voice (Twilio) ──────────────────────────────────────
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    TWILIO_API_KEY: str = ""
    TWILIO_VOICE_WEBHOOK_URL: str = ""

    # ── Payments (Paddle) ────────────────────────────────────────
    PADDLE_CLIENT_TOKEN: str = ""
    PADDLE_API_KEY: str = ""
    PADDLE_WEBHOOK_SECRET: str = ""
    # Paddle Price IDs — override via env when products are created in Paddle dashboard
    # Format: JSON string {"demo_pack": "pri_xxx", "mini_parwa": "pri_xxx", ...}
    PADDLE_PRICE_IDS: str = ""  # Optional: JSON override for all price IDs

    # ── Shopify (F-131) ─────────────────────────────────────────
    SHOPIFY_WEBHOOK_SECRET: str = ""

    # ── Compliance ───────────────────────────────────────────────
    GDPR_RETENTION_DAYS: int = 365
    AUDIT_LOG_RETENTION_DAYS: int = 2555
    DATA_ENCRYPTION_KEY: str = "CHANGE_ME_IN_PROD_32chars!!"  # BC-011: must be overridden in .env

    # ── Validators ────────────────────────────────────────────────

    @field_validator("DATA_ENCRYPTION_KEY")
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        """BC-011: DATA_ENCRYPTION_KEY must be exactly 32 characters."""
        if len(v) != 32:
            raise ValueError(
                f"DATA_ENCRYPTION_KEY must be 32 characters, got {len(v)}"
            )
        return v

    @model_validator(mode="after")
    def _validate_security_defaults(self) -> "Settings":
        """Warn when security-sensitive values are left at defaults.

        In non-production environments, this logs a warning (not an error)
        so development can proceed.  In production, the application MUST
        be configured with proper values — this validator will raise.
        """
        _DEFAULT_PEPPER = "CHANGE_ME_IN_PRODUCTION_p3pp3r!"
        _DEFAULT_ENCRYPTION = "CHANGE_ME_IN_PROD_32chars!!"

        pepper_is_default = self.REFRESH_TOKEN_PEPPER == _DEFAULT_PEPPER
        encryption_is_default = self.DATA_ENCRYPTION_KEY == _DEFAULT_ENCRYPTION

        if self.is_production:
            if pepper_is_default:
                raise ValueError(
                    "REFRESH_TOKEN_PEPPER is still set to its default value. "
                    "This is REQUIRED in production. Set a strong, random "
                    "value (min 32 chars) in your environment."
                )
            if encryption_is_default:
                raise ValueError(
                    "DATA_ENCRYPTION_KEY is still set to its default value. "
                    "This is REQUIRED in production. Set a cryptographically "
                    "random 32-character key in your environment."
                )
        else:
            # Non-production: warn but don't block
            if pepper_is_default:
                warnings.warn(
                    "REFRESH_TOKEN_PEPPER is using its default value. "
                    "Set a proper value before deploying to production.",
                    UserWarning,
                    stacklevel=2,
                )
                logger.warning(
                    "config_default_pepper",
                    extra={
                        "var": "REFRESH_TOKEN_PEPPER",
                        "action": "Using default — set before production",
                    },
                )
            if encryption_is_default:
                warnings.warn(
                    "DATA_ENCRYPTION_KEY is using its default value. "
                    "Set a proper value before deploying to production.",
                    UserWarning,
                    stacklevel=2,
                )
                logger.warning(
                    "config_default_encryption_key",
                    extra={
                        "var": "DATA_ENCRYPTION_KEY",
                        "action": "Using default — set before production",
                    },
                )

        return self

    # ── Feature Flags ────────────────────────────────────────────
    FEATURE_FLAGS_PATH: str = "feature_flags"

    # ── Training ─────────────────────────────────────────────────
    TRAINING_THRESHOLD: int = 50

    # ── Monitoring ───────────────────────────────────────────────
    SENTRY_DSN: str = ""
    GRAFANA_API_KEY: str = ""

    # ── Google OAuth (F-011) ───────────────────────────────────
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # ── GCP Storage (file uploads, model weights) ──────────────
    GCP_STORAGE_BUCKET: str = ""

    # ── Celery (Week 3: BC-004) ────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    CELERY_TASK_ALWAYS_EAGER: bool = False  # testing: sync execution
    CELERY_TASK_EAGER_PROPAGATES: bool = True
    CELERY_WORKER_PREFETCH_MULTIPLIER: int = 1
    CELERY_TASK_ACKS_LATE: bool = True
    CELERY_TASK_REJECT_ON_WORKER_LOST: bool = True
    CELERY_TASK_SOFT_TIME_LIMIT: int = 300  # 5 minutes
    CELERY_TASK_TIME_LIMIT: int = 330  # 5.5 minutes (hard kill)

    # ── CORS (frontend origin) ─────────────────────────────────
    CORS_ORIGINS: str = ""

    # ── Frontend ────────────────────────────────────────────────
    FRONTEND_URL: str = "http://localhost:3000"

    # ── MCP Server ───────────────────────────────────────────────
    MCP_SERVER_URL: str = ""
    MCP_AUTH_TOKEN: str = ""

    # ── Misc ─────────────────────────────────────────────────────
    NEXT_PUBLIC_API_URL: str = ""
    NEXT_PUBLIC_PADDLE_KEY: str = ""
    COLAB_WEBHOOK_URL: str = ""
    MODEL_REGISTRY_PATH: str = "models"

    # ── IP Allowlist (BC-012) ──────────────────────────────────
    IP_ALLOWLIST_ENABLED: bool = False

    # ── Properties ───────────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_test(self) -> bool:
        return self.ENVIRONMENT == "test"


def get_settings() -> Settings:
    """Get settings singleton, forcing required vars via validation."""
    return Settings()  # pydantic raises ValidationError if required missing
