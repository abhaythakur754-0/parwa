"""
Test configuration for unit tests.
Sets up environment variables before any imports.
"""
import os
import sys

# Set environment variables BEFORE any imports - this MUST be at the top
os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost:5432/test_db"
os.environ["SECRET_KEY"] = "test_secret_key_for_unit_tests_not_for_production"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["ENVIRONMENT"] = "test"
# Explicitly unset SENTRY_DSN for unit tests - tests that need it will set it explicitly
os.environ.pop("SENTRY_DSN", None)


def pytest_configure(config):
    """Pytest hook to ensure environment is set before collection."""
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost:5432/test_db"
    os.environ["SECRET_KEY"] = "test_secret_key_for_unit_tests_not_for_production"
    os.environ["REDIS_URL"] = "redis://localhost:6379/0"
    os.environ["ENVIRONMENT"] = "test"
    # Explicitly unset SENTRY_DSN for unit tests
    os.environ.pop("SENTRY_DSN", None)
