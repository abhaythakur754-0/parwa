"""
PARWA Application Configuration

Loads all configuration from environment variables using pydantic-settings.
Required variables (no defaults) per BC-011:
  - SECRET_KEY
  - DATABASE_URL
  - JWT_SECRET_KEY
  - DATA_ENCRYPTION_KEY
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    DATA_ENCRYPTION_KEY: str  # BC-011: required, 32-char key

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
