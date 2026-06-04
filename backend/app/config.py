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
from functools import lru_cache
from typing import Literal, Optional

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
    APP_VERSION: str = "0.3.0"

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

    SECRET_KEY: Optional[str] = None
    DEBUG: bool = False

    # ── Database ─────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./parwa_dev.db"
    REDIS_PASSWORD: str = ""
    REDIS_URL: str = "redis://localhost:6379/0"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        """Normalize DATABASE_URL for SQLAlchemy compatibility.

        - Prisma uses 'file:' prefix for SQLite which SQLAlchemy doesn't
          understand. Convert 'file:/path' to 'sqlite:///path' format.
        - Supabase and many PaaS providers use 'postgres://' but
          SQLAlchemy requires 'postgresql://'. Convert automatically.
        - Handles unencoded '@' in passwords (e.g., Durgamaa@754 → Durgamaa%40754).
        """
        if not v:
            return v
        if v.startswith("file:"):
            path = v[5:]  # strip 'file:'
            # Handle file:/absolute/path → sqlite:////absolute/path (3 slashes + absolute)
            if path.startswith("/"):
                return f"sqlite:///{path}"
            # Handle file:relative/path → sqlite:///relative/path
            return f"sqlite:///{path}"
        # Supabase/Neon/Render often use postgres:// — SQLAlchemy needs postgresql://
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://"):]
        # Fix unencoded '@' in password portion of PostgreSQL URLs.
        # e.g., postgresql://user:Pass@word@host/db → postgresql://user:Pass%40word@host/db
        if v.startswith("postgresql://"):
            try:
                # Split: postgresql://user:password@host:port/db
                prefix = "postgresql://"
                rest = v[len(prefix):]
                # Find the last '@' which separates user:pass from host
                last_at = rest.rfind("@")
                if last_at > 0:
                    user_pass = rest[:last_at]
                    host_db = rest[last_at + 1:]
                    # If user:pass contains '@', the password has unencoded chars
                    if "@" in user_pass:
                        # Split user:pass at first ':'
                        colon_idx = user_pass.find(":")
                        if colon_idx > 0:
                            user = user_pass[:colon_idx]
                            password = user_pass[colon_idx + 1:]
                            # URL-encode '@' in password only
                            encoded_password = password.replace("@", "%40")
                            v = f"{prefix}{user}:{encoded_password}@{host_db}"
                            logger.warning(
                                "DATABASE_URL password contained unencoded '@' — "
                                "auto-encoded to %%40. Please update your env var."
                            )
            except Exception:
                pass  # Don't crash on URL parsing errors
        return v

    # ── JWT (BC-011) ─────────────────────────────────────────────
    JWT_SECRET_KEY: Optional[str] = None
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
    OPENAI_API_KEY: str = ""
    ZAI_API_KEY: str = ""
    ZAI_BASE_URL: str = os.environ.get("ZAI_BASE_URL", "http://localhost:3000/api")
    # LLM Provider: "litellm" (production), "zai_gateway" (dev/testing), "openai" (direct)
    # Auto-detected if empty based on which API keys are set.
    LLM_PROVIDER: str = ""
    LLM_MODEL: str = ""
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
    PADDLE_WEBHOOK_NOTIFICATION_SET_ID: str = ""  # Webhook notification set ID from Paddle dashboard
    # Paddle Price IDs — override via env when products are created in Paddle dashboard
    # Format: JSON string {"demo_pack": "pri_xxx", "mini_parwa": "pri_xxx", ...}
    PADDLE_PRICE_IDS: str = ""  # Optional: JSON override for all price IDs
    PADDLE_NOTIFICATION_SET_ID: str = ""  # Paddle webhook notification set ID

    @field_validator("PADDLE_CLIENT_TOKEN")
    @classmethod
    def validate_paddle_client_token(cls, v: str) -> str:
        if not v:
            warnings.warn(
                "PADDLE_CLIENT_TOKEN is empty — Paddle client-side checkout will not work. "
                "Set PADDLE_CLIENT_TOKEN in production!",
                stacklevel=2,
            )
        return v

    @field_validator("PADDLE_API_KEY")
    @classmethod
    def validate_paddle_api_key(cls, v: str) -> str:
        if not v:
            warnings.warn(
                "PADDLE_API_KEY is empty — Paddle server-side API calls will not work. "
                "Set PADDLE_API_KEY in production!",
                stacklevel=2,
            )
        return v

    @field_validator("PADDLE_WEBHOOK_SECRET")
    @classmethod
    def validate_paddle_webhook_secret(cls, v: str) -> str:
        if not v:
            warnings.warn(
                "PADDLE_WEBHOOK_SECRET is empty — Paddle webhook signatures cannot be verified. "
                "Set PADDLE_WEBHOOK_SECRET in production!",
                stacklevel=2,
            )
        return v

    @field_validator("PADDLE_PRICE_IDS")
    @classmethod
    def validate_paddle_price_ids(cls, v: str) -> str:
        if not v:
            warnings.warn(
                "PADDLE_PRICE_IDS is empty — Paddle product price mapping is not configured. "
                "Set PADDLE_PRICE_IDS in production!",
                stacklevel=2,
            )
        return v

    @field_validator("NEXT_PUBLIC_PADDLE_KEY")
    @classmethod
    def validate_next_public_paddle_key(cls, v: str) -> str:
        if not v:
            warnings.warn(
                "NEXT_PUBLIC_PADDLE_KEY is empty — Paddle frontend integration will not work. "
                "Set NEXT_PUBLIC_PADDLE_KEY in production!",
                stacklevel=2,
            )
        return v

    # ── Shopify (F-131, Day 1 — E-Commerce MCP) ────────────────
    SHOPIFY_WEBHOOK_SECRET: str = ""
    SHOPIFY_API_VERSION: str = "2024-01"
    SHOPIFY_CLIENT_ID: str = ""  # For OAuth flow (future)
    SHOPIFY_CLIENT_SECRET: str = ""  # For OAuth flow (future)
    SHOPIFY_SCOPES: str = "read_orders,write_orders,read_products,read_customers,write_refunds,read_fulfillments"

    # ── Compliance ───────────────────────────────────────────────
    GDPR_RETENTION_DAYS: int = 365
    AUDIT_LOG_RETENTION_DAYS: int = 2555
    DATA_ENCRYPTION_KEY: Optional[str] = None

    # ── Validators ────────────────────────────────────────────────

    @field_validator("DATA_ENCRYPTION_KEY")
    @classmethod
    def validate_encryption_key(cls, v) -> str:
        """BC-011: DATA_ENCRYPTION_KEY should be set and exactly 32 characters.

        Generates a default if not set so the app can start.
        In production, warns loudly if using a default value.
        """
        if v is None or v == "":
            # Generate a stable default so the app can start
            v = "parwa_default_enc_key_32chars!!"
            warnings.warn(
                "DATA_ENCRYPTION_KEY is not set — using insecure default. "
                "Set a 32-character cryptographically random value via "
                "the DATA_ENCRYPTION_KEY env var!",
                stacklevel=2,
            )
        if len(v) != 32:
            if os.environ.get("ENVIRONMENT") == "production":
                warnings.warn(
                    f"DATA_ENCRYPTION_KEY must be 32 characters in production, got {len(v)}. "
                    f"Using as-is but this is insecure.",
                    stacklevel=2,
                )
            else:
                warnings.warn(
                    f"DATA_ENCRYPTION_KEY should be 32 characters, got {len(v)}",
                    stacklevel=2,
                )
        return v

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v) -> str:
        if v is None or v == "":
            # Generate a stable default so the app can start
            v = "parwa_default_sk_2026_change_me_in_prod!"
            warnings.warn(
                "SECRET_KEY is not set — using insecure default. "
                "Set a cryptographically random value via the SECRET_KEY env var!",
                stacklevel=2,
            )
        if v.startswith("dev-") or v == "change-me":
            if os.environ.get("ENVIRONMENT") == "production":
                warnings.warn(
                    "SECRET_KEY is using a default value in production — "
                    "this is insecure! Set a cryptographically random value.",
                    stacklevel=2,
                )
            else:
                warnings.warn(
                    "Using development SECRET_KEY — change in production!",
                    stacklevel=2,
                )
        # Warn about short key length in production
        if os.environ.get("ENVIRONMENT") == "production" and len(v) < 32:
            warnings.warn(
                f"SECRET_KEY should be at least 32 characters in production, "
                f"got {len(v)}. Generate one with: "
                f"python -c \"import secrets; print(secrets.token_urlsafe(32))\"",
                stacklevel=2,
            )
        return v

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_key(cls, v) -> str:
        """C-11 FIX: JWT_SECRET_KEY should be set and changed from default in production.
        Also enforces minimum length in production (>=32 chars).
        Generates a default if not set so the app can start.
        """
        if v is None or v == "":
            # Generate a stable default so the app can start
            v = "parwa_default_jwt_sk_2026_change_me!!"
            warnings.warn(
                "JWT_SECRET_KEY is not set — using insecure default. "
                "Set a cryptographically random value via the JWT_SECRET_KEY env var!",
                stacklevel=2,
            )
        if v.startswith("dev-") or v == "change-me":
            if os.environ.get("ENVIRONMENT") == "production":
                warnings.warn(
                    "JWT_SECRET_KEY is using a default value in production — "
                    "this is insecure! Set a cryptographically random value.",
                    stacklevel=2,
                )
            else:
                warnings.warn(
                    "Using development JWT_SECRET_KEY — change in production!",
                    stacklevel=2,
                )
        # Warn about short key length in production
        if os.environ.get("ENVIRONMENT") == "production" and len(v) < 32:
            warnings.warn(
                f"JWT_SECRET_KEY should be at least 32 characters in production, "
                f"got {len(v)}. Generate one with: "
                f"python -c \"import secrets; print(secrets.token_urlsafe(32))\"",
                stacklevel=2,
            )
        return v

    @field_validator("REDIS_PASSWORD")
    @classmethod
    def validate_redis_password(cls, v: str) -> str:
        if not v:
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

    # ── File Storage ─────────────────────────────────────────────
    STORAGE_BACKEND: str = "local"  # "local" or "gcp"
    STORAGE_LOCAL_PATH: str = "./storage"

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
        """C-11 FIX: MCP_AUTH_TOKEN should be set in production."""
        if not v:
            warnings.warn(
                "MCP_AUTH_TOKEN is empty — MCP server connections are unauthenticated. "
                "Set MCP_AUTH_TOKEN before deploying!",
                stacklevel=2,
            )
        return v

    # ── Pricing Integrity (H-09) ────────────────────────────────
    PRICING_SIGNING_KEY: Optional[str] = None

    @field_validator("PRICING_SIGNING_KEY")
    @classmethod
    def validate_pricing_signing_key(cls, v) -> str:
        if v is None or v == "":
            # Generate a stable default so the app can start
            v = "parwa_default_pricing_sk_change_me!!"
            warnings.warn(
                "PRICING_SIGNING_KEY is not set — using insecure default. "
                "Set a cryptographically random value via the "
                "PRICING_SIGNING_KEY env var!",
                stacklevel=2,
            )
        if v.startswith("dev-"):
            if os.environ.get("ENVIRONMENT") == "production":
                warnings.warn(
                    "PRICING_SIGNING_KEY is using a default value in production — "
                    "this is insecure! Set a cryptographically random value.",
                    stacklevel=2,
                )
            else:
                warnings.warn(
                    "Using development PRICING_SIGNING_KEY — change in production!",
                    stacklevel=2,
                )
        # Warn about short key length in production
        if os.environ.get("ENVIRONMENT") == "production" and len(v) < 32:
            warnings.warn(
                f"PRICING_SIGNING_KEY should be at least 32 characters in production, "
                f"got {len(v)}. Generate one with: "
                f"python -c \"import secrets; print(secrets.token_urlsafe(32))\"",
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

    # ── Operational Tuning (R-07) ──────────────────────────────────
    # Previously hardcoded in individual routers — now configurable
    # via environment variables so ops teams can tune without code changes.

    # Pricing token validity (was hardcoded 3600 in pricing.py)
    PRICING_TOKEN_TTL_SECONDS: int = 3600

    # Pricing max quantity per variant (was hardcoded 10 in pricing.py)
    PRICING_MAX_VARIANT_QUANTITY: int = 10

    # Pricing input sanitization max length (was hardcoded 100 in pricing.py)
    PRICING_INPUT_MAX_LENGTH: int = 100

    # MFA session TTL (was hardcoded 300 in mfa.py)
    MFA_SESSION_TTL_SECONDS: int = 300

    # Knowledge Base file upload limits (was hardcoded in knowledge_base.py)
    KB_MAX_FILE_SIZE: int = 52428800  # 50 MB
    KB_MAX_RETRY_COUNT: int = 3

    # Webhook limits (was hardcoded in webhooks.py)
    WEBHOOK_MAX_PAYLOAD_SIZE: int = 1048576  # 1 MB
    WEBHOOK_MAX_AGE_SECONDS: int = 300  # 5 minutes

    # Webhook payload max size for status/retry responses
    WEBHOOK_STATUS_INCLUDE_PAYLOAD: bool = False

    # ── Email Channel Tuning (CH-02) ──────────────────────────────
    # Previously hardcoded MAX_REPLY_DEPTH = 20 in email_channel_service.py
    # Now configurable per-tenant via environment variable.
    EMAIL_MAX_REPLY_DEPTH: int = 20

    # ── Email Circuit Breaker Tuning (CH-03) ─────────────────────
    # Previously hardcoded as global _cb_state in email_service.py
    # Now configurable so ops can tune thresholds without code changes.
    EMAIL_CB_FAILURE_THRESHOLD: int = 3
    EMAIL_CB_RESET_SECONDS: int = 60

    # ── Properties ───────────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_test(self) -> bool:
        return self.ENVIRONMENT == "test"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings singleton, forcing required vars via validation."""
    return Settings()  # pydantic raises ValidationError if required missing
