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

    @field_validator("REDIS_URL", "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND", mode="before")
    @classmethod
    def normalize_redis_ssl_url(cls, v: str) -> str:
        """Normalize Redis URLs.

        - Upstash URLs (contain 'upstash.io') REQUIRE rediss:// (TLS) — keep as-is.
        - Render internal Redis uses rediss:// but doesn't have TLS → convert to redis://.
        - Plain redis:// URLs pass through unchanged.
        """
        if not v or not isinstance(v, str):
            return v
        # Upstash requires TLS — don't strip rediss://
        if "upstash" in v.lower():
            return v
        # Render internal Redis — convert rediss:// to redis://
        if v.startswith("rediss://"):
            v = "redis://" + v[len("rediss://"):]
        return v

    # ── JWT (BC-011) ─────────────────────────────────────────────
    JWT_SECRET_KEY: Optional[str] = None
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
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
    NVIDIA_API_KEY: str = ""

    # ── Superglue (universal integration layer) ──────────────────
    SUPERGLUE_API_URL: str = ""
    SUPERGLUE_AUTH_TOKEN: str = ""

    LLM_PRIMARY_PROVIDER: str = "google"
    LLM_FALLBACK_PROVIDER: str = "groq"
    AI_LIGHT_MODEL: str = "groq/llama-3.1-8b"
    AI_MEDIUM_MODEL: str = "groq/llama-3.1-8b"
    AI_HEAVY_MODEL: str = "groq/gpt-oss-120b"
    AI_FAILOVER_MODEL: str = "groq/llama-3.1-8b"

    # ── Email (Brevo) ────────────────────────────────────────────
    BREVO_API_KEY: str = ""
    FROM_EMAIL: str = "noreply@parwa.buzz"
    # Comma-separated CIDR ranges for Brevo inbound webhook IP allowlist.
    # Falls back to DEFAULT_BREVO_IPS in hmac_verification.py if empty.
    BREVO_INBOUND_IPS: str = ""

    # ── SMS/Voice (Twilio) ──────────────────────────────────────
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    TWILIO_API_KEY: str = ""
    TWILIO_VOICE_WEBHOOK_URL: str = ""

    # ── Payments (Razorpay) ────────────────────────────────────
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""
    RAZORPAY_TEST_MODE: str = "true"

    # NOTE: Paddle was removed on 2026-06-24. Razorpay is the billing provider.
    # (See RAZORPAY_* settings above and app.clients.razorpay_client.)

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
        """BC-011: DATA_ENCRYPTION_KEY must be set and at least 32 characters.

        Auto-generates a 32-char key if not set (all environments).
        In production: logs a loud warning instead of crashing, because
        a running app with auto-generated keys is better than a dead app.
        """
        if v is None or v == "":
            import secrets as _secrets
            v = _secrets.token_urlsafe(24)[:32]  # exactly 32 chars
            env = os.environ.get("ENVIRONMENT", "development")
            if env == "production":
                warnings.warn(
                    "SECURITY: DATA_ENCRYPTION_KEY not set in production — "
                    "auto-generated! This means encrypted data will be lost on "
                    "restart. Set a 32-character value via DATA_ENCRYPTION_KEY env var!",
                    stacklevel=2,
                )
            else:
                warnings.warn(
                    "DATA_ENCRYPTION_KEY not set — auto-generated for development.",
                    stacklevel=2,
                )
        # AES-256-GCM uses SHA-256 to derive the key, so any length >= 32 is fine.
        # The old validator required exactly 32 chars, but longer keys are also valid
        # because derive_key() in security.py uses hashlib.sha256().digest() which
        # always produces exactly 32 bytes regardless of input length.
        if len(v) < 32:
            warnings.warn(
                f"DATA_ENCRYPTION_KEY should be at least 32 characters, got {len(v)}",
                stacklevel=2,
            )
        return v

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v) -> str:
        """BC-011: SECRET_KEY must be set and strong in production.

        Auto-generates a 32-char key if not set (development only).
        In production:
          - RAISES if the value is a known default ("dev-...", "change-me")
          - RAISES if the value is shorter than 16 chars
          - Warns (but still runs) if unset — auto-generated key means
            sessions invalidate on restart, which is annoying but not
            a security hole.
        """
        env = os.environ.get("ENVIRONMENT", "development")
        if v is None or v == "":
            import secrets as _secrets
            v = _secrets.token_urlsafe(32)
            if env == "production":
                warnings.warn(
                    "SECURITY: SECRET_KEY not set in production — "
                    "auto-generated! Sessions will be invalidated on restart. "
                    "Set via SECRET_KEY env var!",
                    stacklevel=2,
                )
            else:
                warnings.warn(
                    "SECRET_KEY not set — auto-generated for development.",
                    stacklevel=2,
                )
        # CRITICAL: known default secrets must never run in production.
        # These values are committed to the public repo — attackers can
        # forge session tokens if the backend accepts them.
        if v.startswith("dev-") or v == "change-me":
            if env == "production":
                raise ValueError(
                    "SECURITY CRITICAL (C-06): SECRET_KEY is a known default "
                    f"({v!r}) in production. This value is public in the repo "
                    "and lets attackers forge session tokens. "
                    "Set a strong SECRET_KEY via the SECRET_KEY env var."
                )
            warnings.warn(
                "Using development SECRET_KEY — change in production!",
                stacklevel=2,
            )
        # CRITICAL: too-short keys are brute-forceable. Refuse to start.
        if env == "production" and len(v) < 16:
            raise ValueError(
                f"SECURITY CRITICAL (C-06): SECRET_KEY is only {len(v)} chars "
                "in production — minimum 16 required (32+ recommended). "
                "Set a strong SECRET_KEY via the SECRET_KEY env var."
            )
        # Warn (not crash) if shorter than recommended 32 chars
        if env == "production" and len(v) < 32:
            warnings.warn(
                f"SECURITY: SECRET_KEY is only {len(v)} chars — "
                f"should be at least 32 for production!",
                stacklevel=2,
            )
        return v

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_key(cls, v) -> str:
        """BC-011: JWT_SECRET_KEY must be set and strong in production.

        In production:
          - RAISES if unset (auto-generation would silently invalidate
            every JWT on each restart and is unsafe for a multi-tenant
            SaaS — operators must explicitly set the key)
          - RAISES if the value is a known default ("dev-...", "change-me")
          - RAISES if the value is shorter than 16 chars
        In development: auto-generates a 32-char key if not set.
        """
        env = os.environ.get("ENVIRONMENT", "development")
        if v is None or v == "":
            if env == "production":
                # CRITICAL: an auto-generated JWT secret in production means
                # every signed token invalidates on each restart AND the
                # operator has no visibility into the key. Worse, an attacker
                # who reads a single token can replay it until the next
                # restart. Refuse to start.
                raise ValueError(
                    "SECURITY CRITICAL (C-06): JWT_SECRET_KEY is not set in "
                    "production. Set a strong (32+ char) value via the "
                    "JWT_SECRET_KEY env var. Auto-generation is disabled in "
                    "production because it silently invalidates all user "
                    "sessions on every restart."
                )
            import secrets as _secrets
            v = _secrets.token_urlsafe(32)
            warnings.warn(
                "JWT_SECRET_KEY not set — auto-generated for development.",
                stacklevel=2,
            )
        # CRITICAL: known default secrets must never run in production.
        # These values are committed to the public repo — attackers can
        # forge any JWT (including is_platform_admin=true) if accepted.
        if v.startswith("dev-") or v == "change-me":
            if env == "production":
                raise ValueError(
                    "SECURITY CRITICAL (C-06): JWT_SECRET_KEY is a known "
                    f"default ({v!r}) in production. This value is public in "
                    "the repo and lets attackers forge JWTs with arbitrary "
                    "claims (including is_platform_admin=true). Set a strong "
                    "JWT_SECRET_KEY via the JWT_SECRET_KEY env var."
                )
            warnings.warn(
                "Using development JWT_SECRET_KEY — change in production!",
                stacklevel=2,
            )
        # CRITICAL: too-short keys are brute-forceable. Refuse to start.
        if env == "production" and len(v) < 16:
            raise ValueError(
                f"SECURITY CRITICAL (C-06): JWT_SECRET_KEY is only {len(v)} "
                "chars in production — minimum 16 required (32+ recommended). "
                "Set a strong JWT_SECRET_KEY via the JWT_SECRET_KEY env var."
            )
        # Warn (not crash) if shorter than recommended 32 chars
        if env == "production" and len(v) < 32:
            warnings.warn(
                f"SECURITY: JWT_SECRET_KEY is only {len(v)} chars — "
                f"should be at least 32 for production!",
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
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"  # Render Redis only supports DB 0
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    CELERY_TASK_ALWAYS_EAGER: bool = False  # testing: sync execution
    CELERY_TASK_EAGER_PROPAGATES: bool = True
    CELERY_WORKER_PREFETCH_MULTIPLIER: int = 1
    CELERY_TASK_ACKS_LATE: bool = True
    CELERY_TASK_REJECT_ON_WORKER_LOST: bool = True
    CELERY_TASK_SOFT_TIME_LIMIT: int = 300  # 5 minutes
    CELERY_TASK_TIME_LIMIT: int = 330  # 5.5 minutes (hard kill)

    # ── CORS (frontend origin) ─────────────────────────────────
    CORS_ORIGINS: str = "http://localhost:3000,https://parwa.buzz,https://parwa.vercel.app"

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

    # ── Delivery Pipeline Tuning (BC-015) ───────────────────────────
    # Node 6.5 Deliver — production hardening knobs. All env-var driven
    # so ops can tune without redeploy. See BC-015 in CLAUDE.md.
    DELIVERY_SMS_CHAR_LIMIT: int = 1600              # 10-segment x 160 GSM-7
    DELIVERY_MAX_RETRIES: int = 3                    # per-channel retries before fallback
    DELIVERY_BACKOFF_BASE_SECONDS: float = 1.0       # exponential backoff base
    DELIVERY_BACKOFF_MAX_SECONDS: float = 10.0       # backoff cap
    DELIVERY_CB_FAILURE_THRESHOLD: int = 5           # per-channel failures before CB opens
    DELIVERY_CB_RESET_SECONDS: int = 120             # CB half-open cooldown
    DELIVERY_DLQ_QUEUE_NAME: str = "parwa_dlq"       # reuse existing Celery DLQ
    DELIVERY_AUDIT_ENABLED: bool = True              # write audit rows on every attempt
    DELIVERY_METRICS_ENABLED: bool = True            # emit Prometheus counters
    DELIVERY_TIMEOUT_SECONDS: int = 30               # per-dispatch wall-clock cap

    # ── Node 6.5 Phase 2 — CRM push-back (BC-016) ─────────────────
    # After customer dispatch succeeds, push "resolved" status back to the
    # originating CRM (Zendesk/HubSpot/Generic). CRM push is best-effort:
    # if it fails, we persist to DLQ with error_type=crm_push_failed so
    # ops can replay. Customer already received the answer, so this is a
    # consistency issue, not a delivery issue.
    CRM_PUSH_ENABLED: bool = True                    # master switch
    CRM_PUSH_MAX_RETRIES: int = 2                    # retries before DLQ
    CRM_PUSH_BACKOFF_BASE_SECONDS: float = 2.0       # CRM APIs are flakier than email
    CRM_PUSH_BACKOFF_MAX_SECONDS: float = 30.0
    CRM_PUSH_TIMEOUT_SECONDS: int = 15               # CRM APIs should respond fast
    CRM_PUSH_DLQ_ON_FAILURE: bool = True             # persist to DLQ on all-retries-exhausted

    # ── BC-017: Escalation CRM push-back (Node 8 + guidance flow) ──
    # Two additional CRM transitions are made production-ready:
    #   1. push_escalation (Node 8)  — fire-and-forget → retry + DLQ
    #   2. push_resume_result        — fire-and-forget → retry + DLQ
    #   3. push_permanent_failure    — NEW: reset CRM to "open/new" when
    #      AI exhausts MAX_GUIDANCE_RETRIES attempts and gives up.
    #    This means: when AI can't solve, CRM ticket goes back to "new"
    #    in the human queue (with tags + internal note explaining why),
    #    exactly like before PARWA touched it.
    GUIDANCE_MAX_RETRIES: int = 3                    # max guidance attempts before permanent failure
    GUIDANCE_CRM_DLQ_ON_FAILURE: bool = True         # persist resume/escalation push to DLQ on fail

    @field_validator("DELIVERY_SMS_CHAR_LIMIT")
    @classmethod
    def validate_delivery_sms_limit(cls, v: int) -> int:
        if v < 160:
            raise ValueError("DELIVERY_SMS_CHAR_LIMIT must be >= 160 (one segment)")
        return v

    @field_validator("DELIVERY_MAX_RETRIES")
    @classmethod
    def validate_delivery_retries(cls, v: int) -> int:
        if v < 0 or v > 10:
            raise ValueError("DELIVERY_MAX_RETRIES must be in [0, 10]")
        return v

    @field_validator("DELIVERY_BACKOFF_BASE_SECONDS")
    @classmethod
    def validate_delivery_backoff_base(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("DELIVERY_BACKOFF_BASE_SECONDS must be > 0")
        return v

    @field_validator("GUIDANCE_MAX_RETRIES")
    @classmethod
    def validate_guidance_max_retries(cls, v: int) -> int:
        if v < 1 or v > 10:
            raise ValueError("GUIDANCE_MAX_RETRIES must be in [1, 10]")
        return v

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
