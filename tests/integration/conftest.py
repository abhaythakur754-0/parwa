"""
Custom conftest for Phase 2+ integration tests.
Overrides the default conftest that tries to init_db with SQLite-incompatible models.

Integration tests run against the LIVE backend at localhost:8000.
They do NOT import the app module or run init_db — all requests go through HTTP.
"""
import sys
import os

# Prevent the default conftest from running init_db by setting env vars BEFORE imports
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:////home/z/my-project/parwa/db/custom.db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_for_integration_testing_12345")
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_integration_testing_12345")
os.environ.setdefault("DATA_ENCRYPTION_KEY", "12345678901234567890123456789012")
os.environ.setdefault("PRICING_SIGNING_KEY", "test_pricing_signing_key_1234567890")
os.environ.setdefault("REDIS_URL", "")

# CRITICAL: Skip the root conftest.py which tries to import and init_db
# This is needed because pytest collects conftest.py from parent directories
# and the root conftest.py tries to call init_db() which fails with JSONB on SQLite
def pytest_configure(config):
    """Override root conftest's init_db by not importing it."""
    pass
