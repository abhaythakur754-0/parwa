"""
PARWA Test Configuration

Shared fixtures for all tests. Sets ENVIRONMENT=test before imports.
"""

import os

import pytest

# MUST be set BEFORE importing any app module
os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test_secret_key_for_testing_only_not_prod"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_not_prod"
os.environ["DATA_ENCRYPTION_KEY"] = "12345678901234567890123456789012"

from backend.app.main import app  # noqa: E402
from database.base import init_db  # noqa: E402

# Create all tables for tests (SQLite in-memory)
init_db()


@pytest.fixture
def client():
    """Sync test client for FastAPI app."""
    from starlette.testclient import TestClient
    return TestClient(app)


@pytest.fixture
def client_no_raise():
    """Test client that does not raise exceptions on 500 errors."""
    from starlette.testclient import TestClient
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset rate limiter singleton between tests to prevent test pollution."""
    from backend.app.services.rate_limit_service import (
        get_rate_limit_service,
    )
    svc = get_rate_limit_service()
    svc._in_memory.clear()
    svc._failures.clear()
    yield
