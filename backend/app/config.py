"""
PARWA Application Configuration

Loads all configuration from environment variables using pydantic-settings.
Sensible dev defaults are provided so the app starts without a .env file.
Validators warn (not crash) if dev defaults are used in production.
"""

import logging
import os
import warnings
from enum import Enum
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Environment(str, Enum):
    """Valid application environment values."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    TEST = "test"
    PRODUCTION = "production"


# Valid environment values as a Literal union for pydantic validation
_VALID_ENVIRONMENTS = Literal[
    "development",
    "staging",
    "test",
    "production",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────
    ENVIRONMENT: str = "development"

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Ensure ENVIRONMENT is one of the allowed values."""
        valid = {e.value for e in Environment}
        if v not in valid:
            raise ValueError(
                f"ENVIRONMENT must be one of {sorted(valid)}, got '{v}'"
            )
        return v

    SECRET_KEY: str = "dev-secret-key-change-in-production"
    DEBUG: bool = False

    # ── Database ─────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./parwa_dev.db"
    REDIS_PASSWORD: str = ""
    REDIS_URL: str = "redis://localhost:6379/0"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        """Normalize DATABASE_URL for SQLAlchemy compatibility.

        Prisma uses 'file:' prefix for SQLite which SQLAlchemy doesn't
        understand. Convert 'file:/path' to 'sqlite:///path' format.
        """
        if v and v.startswith("file:"):
            path = v[5:]  # strip 'file:'
            # Handle file:/absolute/path → sqlite:////absolute/path (3 slashes + absolute)
            if path.startswith("/"):
                return f"sqlite:///{path}"
            # Handle file:relative/path → sqlite:///relative/path
            return f"sqlite:///{path}"
        return v

    # ── JWT (BC-011) ─────────────────────────────────────────────
    JWT_SECRET_KEY: str = "dev-jwt-secret-key-change-in-production"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    MAX_SESSIONS_PER_USER: int = 5

    # ── JWT RS256 (Week 6) ───────────────────────────────────────
    JWT_ALGORITHM: str = "HS256"  # "HS256" or "RS256"
    JWT_PRIVATE_KEY_PATH: str = ""  # Path to RSA private key PEM file
    JWT_PUBLIC_KEY_PATH: str = ""  # Path to RSA public key PEM file
    JWT_PRIVATE_KEY_BASE64: str = ""  # Base64-encoded RSA private key (alternative to file)
    JWT_PUBLIC_KEY_BASE64: str = ""  # Base64-encoded RSA public key (alternative to file)
    JWT_KID: str = "parwa-key-v1"  # Key ID for JWT header

    @field_validator("JWT_ALGORITHM")
    @classmethod
    def validate_jwt_algorithm(cls, v: str) -> str:
        if v not in ("HS256", "RS256"):
            raise ValueError(
                f"JWT_ALGORITHM must be 'HS256' or 'RS256', got '{v}'"
            )
        return v

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
    DATA_ENCRYPTION_KEY: str = "devkey_devkey_devkey_devkey_abcd"  # 32-char dev default

    # ── Validators ────────────────────────────────────────────────

    @field_validator("DATA_ENCRYPTION_KEY")
    @classmethod
    def validate_encryption_key(cls, v: str) -> str:
        """BC-011: DATA_ENCRYPTION_KEY must be exactly 32 characters."""
        if len(v) != 32:
            if os.environ.get("ENVIRONMENT") == "production":
                raise ValueError(
                    f"DATA_ENCRYPTION_KEY must be 32 characters in production, got {len(v)}"
                )
            warnings.warn(
                f"DATA_ENCRYPTION_KEY should be 32 characters, got {len(v)}",
                stacklevel=2,
            )
        return v

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if v.startswith("dev-") or v == "change-me":
            if os.environ.get("ENVIRONMENT") == "production":
                raise ValueError(
                    "SECRET_KEY must be changed from default in production. "
                    "Set a cryptographically random value via the SECRET_KEY env var."
                )
            warnings.warn(
                "Using development SECRET_KEY — change in production!",
                stacklevel=2,
            )
        return v

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_key(cls, v: str) -> str:
        """C-11 FIX: JWT_SECRET_KEY must be changed from default in production.
        Also enforces minimum length in production (>=32 chars).
        """
        if v.startswith("dev-") or v == "change-me":
            if os.environ.get("ENVIRONMENT") == "production":
                raise ValueError(
                    "JWT_SECRET_KEY must be changed from default in production. "
                    "Set a cryptographically random value via the JWT_SECRET_KEY env var."
                )
            warnings.warn(
                "Using development JWT_SECRET_KEY — change in production!",
                stacklevel=2,
            )
        # C-11 FIX: Enforce minimum key length in production
        if os.environ.get("ENVIRONMENT") == "production" and len(v) < 32:
            raise ValueError(
                f"JWT_SECRET_KEY must be at least 32 characters in production, "
                f"got {len(v)}. Generate one with: "
                f"python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        return v

    @field_validator("REDIS_PASSWORD")
    @classmethod
    def validate_redis_password(cls, v: str) -> str:
        if not v:
            if os.environ.get("ENVIRONMENT") == "production":
                raise ValueError(
                    "REDIS_PASSWORD must be set in production. "
                    "Set a strong password via the REDIS_PASSWORD env var."
                )
            warnings.warn(
                "REDIS_PASSWORD is empty — Redis is unauthenticated. "
                "Set REDIS_PASSWORD in production!",
                stacklevel=2,
            )
        return v

    # ── Feature Flags ────────────────────────────────────────────
    FEATURE_FLAGS_PATH: str = "feature_flags"

    # ── Training ─────────────────────────────────────────────────
    TRAINING_THRESHOLD: int = 50

    # ── Monitoring ───────────────────────────────────────────────
    SENTRY_DSN: str = ""
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1
    SENTRY_PROFILES_SAMPLE_RATE: float = 0.1
    SENTRY_ENVIRONMENT: str = ""  # Falls back to ENVIRONMENT if empty
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

    @field_validator("MCP_AUTH_TOKEN")
    @classmethod
    def validate_mcp_auth_token(cls, v: str) -> str:
        """C-11 FIX: MCP_AUTH_TOKEN must be set in production."""
        if not v:
            if os.environ.get("ENVIRONMENT") == "production":
                raise ValueError(
                    "MCP_AUTH_TOKEN is REQUIRED in production. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
                )
            warnings.warn(
                "MCP_AUTH_TOKEN is empty — MCP server connections are unauthenticated. "
                "Set MCP_AUTH_TOKEN before deploying!",
                stacklevel=2,
            )
        return v

    # ── Pricing Integrity (H-09) ────────────────────────────────
    PRICING_SIGNING_KEY: str = "dev-pricing-key-change-in-prod-32c"

    @field_validator("PRICING_SIGNING_KEY")
    @classmethod
    def validate_pricing_signing_key(cls, v: str) -> str:
        if not v or v.startswith("dev-"):
            if os.environ.get("ENVIRONMENT") == "production":
                raise ValueError(
                    "PRICING_SIGNING_KEY must be set to a non-default value "
                    "in production. Set a cryptographically random value via the "
                    "PRICING_SIGNING_KEY env var."
                )
            warnings.warn(
                "Using development PRICING_SIGNING_KEY — change in production!",
                stacklevel=2,
            )
        return v

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
