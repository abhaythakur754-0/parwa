"""
PARWA MCP Server Configuration

Loads MCP-specific configuration from environment variables.
Defaults to development settings when running outside Docker.

C-04 FIX: MCP_AUTH_TOKEN now raises in production if not set.
C-05 FIX: cors_origin_list no longer returns ["*"] as fallback.
"""

import os
import warnings

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class MCPSettings(BaseSettings):
    """MCP Server settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # ── MCP Server Identity ──────────────────────────────────────
    MCP_SERVER_NAME: str = "parwa-mcp"
    MCP_SERVER_VERSION: str = "1.0.0"
    MCP_SERVER_PORT: int = 8080
    MCP_SERVER_HOST: str = "0.0.0.0"

    # ── Backend Connection ───────────────────────────────────────
    # URL of the main PARWA backend API
    BACKEND_URL: str = "http://localhost:5100"
    # Auth token for backend-to-MCP communication
    MCP_AUTH_TOKEN: str = ""

    # ── Database ─────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./parwa_dev.db"
    REDIS_URL: str = "redis://localhost:6379/0"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        """Normalize DATABASE_URL for SQLAlchemy compatibility."""
        if v and v.startswith("file:"):
            path = v[5:]
            if path.startswith("/"):
                return f"sqlite:///{path}"
            return f"sqlite:///{path}"
        return v

    # ── CORS ─────────────────────────────────────────────────────
    CORS_ORIGINS: str = ""

    # ── Logging ──────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    # ── Validators ────────────────────────────────────────────────

    @field_validator("MCP_AUTH_TOKEN")
    @classmethod
    def validate_auth_token(cls, v: str) -> str:
        """C-04 FIX: MCP_AUTH_TOKEN is required in production."""
        if not v:
            env = os.environ.get("ENVIRONMENT", "development")
            if env == "production":
                raise ValueError(
                    "MCP_AUTH_TOKEN is REQUIRED in production. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
                )
            warnings.warn(
                "MCP_AUTH_TOKEN is empty — all MCP requests are allowed "
                "without authentication. Set MCP_AUTH_TOKEN before deploying!",
                stacklevel=2,
            )
        return v

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Also validate MCP_AUTH_TOKEN when ENVIRONMENT is set to production."""
        # If environment is being set to production, ensure MCP_AUTH_TOKEN is also set
        if v == "production":
            token = os.environ.get("MCP_AUTH_TOKEN", "")
            if not token:
                raise ValueError(
                    "MCP_AUTH_TOKEN is REQUIRED when ENVIRONMENT=production. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
                )
        return v

    # ── Properties ───────────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_test(self) -> bool:
        return self.ENVIRONMENT == "test"

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse CORS_ORIGINS into a list.

        C-05 FIX: Never returns ["*"]. If no origins are configured,
        returns an empty list (which denies all cross-origin requests).
        This prevents the wildcard + credentials security violation.
        """
        if self.CORS_ORIGINS:
            return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
        # C-05 FIX: Return empty list instead of ["*"]
        # An empty list means all cross-origin requests are denied,
        # which is the safe default. Configure CORS_ORIGINS explicitly.
        return []


def get_settings() -> MCPSettings:
    """Get MCP settings singleton."""
    return MCPSettings()
