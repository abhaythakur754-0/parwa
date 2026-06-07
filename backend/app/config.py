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

        1. Prisma uses 'file:' prefix for SQLite which SQLAlchemy doesn't
           understand. Convert 'file:/path' to 'sqlite:///path' format.
        2. PostgreSQL URLs with '@' in the password need the '@' URL-encoded
           as '%40' so SQLAlchemy's URL parser doesn't split the password
           at the wrong position. This handles the common case where a
           Supabase/Render DATABASE_URL has a password like 'Pass@123'.
        """
        if v and v.startswith("file:"):
            path = v[5:]  # strip 'file:'
            # Handle file:/absolute/path → sqlite:////absolute/path (3 slashes + absolute)
            if path.startswith("/"):
                return f"sqlite:///{path}"
            # Handle file:relative/path → sqlite:///relative/path
            return f"sqlite:///{path}"

        # PostgreSQL URL: fix unencoded '@' in password
        # Strategy: count '@' symbols. A valid PG URL has exactly one '@'
        # separating credentials from host. If there are 2+, the extra '@'
        # must be in the password and needs encoding as %40.
        if v and v.startswith("postgresql"):
            at_count = v.count("@")
            if at_count > 1:
                # Find the scheme:// prefix end
                scheme_end = v.find("://") + 3
                rest = v[scheme_end:]
                # Split from the RIGHT — last '@' is the credential/host separator
                # Everything after the last '@' is host:port/db
                last_at = rest.rfind("@")
                credentials_part = rest[:last_at]
                host_part = rest[last_at + 1:]  # skip the '@'
                # Encode any '@' within credentials (user:password)
                from urllib.parse import quote
                credentials_encoded = credentials_part.replace("@", "%40")
                # But wait — only the password should have @ encoded, not the
                # user:password separator. Let's be more precise:
                # credentials format: username:password
                if ":" in credentials_encoded:
                    user_part, pass_part = credentials_encoded.split(":", 1)
                    pass_encoded = pass_part.replace("@", "%40")
                    credentials_encoded = f"{user_part}:{pass_encoded}"
                v = f"{v[:scheme_end]}{credentials_encoded}@{host_part}"

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

    # ── Shopify (F-131) ─────────────────────────────────────────
    SHOPIFY_WEBHOOK_SECRET: str = ""

    # ── Compliance ───────────────────────────────────────────────
    GDPR_RETENTION_DAYS: int = 365
    AUDIT_LOG_RETENTION_DAYS: int = 2555
    DATA_ENCRYPTION_KEY: Optional[str] = None

    # ── Validators ────────────────────────────────────────────────

    @field_validator("DATA_ENCRYPTION_KEY")
    @classmethod
    def validate_encryption_key(cls, v) -> str:
        """BC-011: DATA_ENCRYPTION_KEY must be set and exactly 32 characters.

        In development/staging/test: auto-generates a 32-char key if not set,
        so the app doesn't crash on startup. Warns that it should be set.
        In production: raises ValueError if not set or wrong length.
        """
        env = os.environ.get("ENVIRONMENT", "development")
        if v is None or v == "":
            if env == "production":
                raise ValueError(
                    "DATA_ENCRYPTION_KEY must be set in production. "
                    "Set a 32-character cryptographically random value via "
                    "the DATA_ENCRYPTION_KEY env var."
                )
            # Auto-generate for dev/staging/test so app doesn't crash
            import secrets as _secrets
            v = _secrets.token_urlsafe(24)[:32]  # exactly 32 chars
            warnings.warn(
                "DATA_ENCRYPTION_KEY not set — auto-generated for development. "
                "Set a 32-character value via DATA_ENCRYPTION_KEY env var in production!",
                stacklevel=2,
            )
        if len(v) != 32:
            if env == "production":
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
    def validate_secret_key(cls, v) -> str:
        """BC-011: SECRET_KEY must be set and strong in production.

n        In development/staging/test: auto-generates a 32-char key if not set,
        so the app doesn't crash on startup. Warns that it should be set.
        In production: raises ValueError if not set or too weak.
        """
        env = os.environ.get("ENVIRONMENT", "development")
        if v is None or v == "":
            if env == "production":
                raise ValueError(
                    "SECRET_KEY must be set in production. "
                    "Set a cryptographically random value via the SECRET_KEY env var."
                )
            # Auto-generate for dev/staging/test so app doesn't crash
            import secrets as _secrets
            v = _secrets.token_urlsafe(32)
            warnings.warn(
                "SECRET_KEY not set — auto-generated for development. "
                "Set a cryptographically random value via SECRET_KEY env var in production!",
                stacklevel=2,
            )
        if v.startswith("dev-") or v == "change-me":
            if env == "production":
                raise ValueError(
                    "SECRET_KEY must be changed from default in production. "
                    "Set a cryptographically random value via the SECRET_KEY env var."
                )
            warnings.warn(
                "Using development SECRET_KEY — change in production!",
                stacklevel=2,
            )
        # Enforce minimum key length in production
        if env == "production" and len(v) < 32:
            raise ValueError(
                f"SECRET_KEY must be at least 32 characters in production, "
                f"got {len(v)}. Generate one with: "
                f"python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        return v

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_key(cls, v) -> str:
        """BC-011: JWT_SECRET_KEY must be set and strong in production.

        In development/staging/test: auto-generates a 32-char key if not set,
        so the app doesn't crash on startup. Warns that it should be set.
        In production: raises ValueError if not set or too weak.
        """
        env = os.environ.get("ENVIRONMENT", "development")
        if v is None or v == "":
            if env == "production":
                raise ValueError(
                    "JWT_SECRET_KEY must be set in production. "
                    "Set a cryptographically random value via the JWT_SECRET_KEY env var."
                )
            # Auto-generate for dev/staging/test so app doesn't crash
            import secrets as _secrets
            v = _secrets.token_urlsafe(32)
            warnings.warn(
                "JWT_SECRET_KEY not set — auto-generated for development. "
                "Set a cryptographically random value via JWT_SECRET_KEY env var in production!",
                stacklevel=2,
            )
        if v.startswith("dev-") or v == "change-me":
            if env == "production":
                raise ValueError(
                    "JWT_SECRET_KEY must be changed from default in production. "
                    "Set a cryptographically random value via the JWT_SECRET_KEY env var."
                )
            warnings.warn(
                "Using development JWT_SECRET_KEY — change in production!",
                stacklevel=2,
            )
        # Enforce minimum key length in production
        if env == "production" and len(v) < 32:
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
    CORS_ORIGINS: str = "http://localhost:3000,https://parwa.buzz,https://parwa.ai,https://parwa.vercel.app"

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
            warnings.warn(
                "PRICING_SIGNING_KEY is not set — pricing token signing is disabled. "
                "Set a cryptographically random value via the PRICING_SIGNING_KEY env var.",
                stacklevel=2,
            )
            return v
        if v.startswith("dev-"):
            warnings.warn(
                "Using development PRICING_SIGNING_KEY — change in production!",
                stacklevel=2,
            )
        # Enforce minimum key length in production
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
