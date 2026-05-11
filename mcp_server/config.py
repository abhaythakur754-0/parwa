"""
PARWA MCP Server Configuration

Loads MCP-specific configuration from environment variables.
Defaults to development settings when running outside Docker.
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
        if not v and os.environ.get("ENVIRONMENT") == "production":
            warnings.warn(
                "MCP_AUTH_TOKEN is empty — set in production for security",
                stacklevel=2,
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
        """Parse CORS_ORIGINS into a list."""
        if self.CORS_ORIGINS:
            return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
        return ["*"]


def get_settings() -> MCPSettings:
    """Get MCP settings singleton."""
    return MCPSettings()
