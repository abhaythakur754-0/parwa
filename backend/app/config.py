import os


class Settings:
    """Application configuration loaded from environment variables.

    Every setting has a sensible default for local development.
    Production deployments MUST override secrets via environment variables.
    """

    PROJECT_NAME: str = "PARWA"
    VERSION: str = "3.0.0"
    API_V1_PREFIX: str = "/api/v1"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./parwa.db")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    ENCRYPTION_MASTER_KEY: str = os.getenv(
        "ENCRYPTION_MASTER_KEY",
        "dev-master-key-change-in-production-32ch",
    )
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-jwt-secret-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:8000"]


settings = Settings()
