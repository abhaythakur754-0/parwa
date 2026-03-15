"""
Root conftest.py — ensures the project root is on sys.path for all tests.
This allows `from shared.X import ...` and `from backend.X import ...`
to resolve correctly both locally and in CI.

Also sets up environment variables before any imports.
"""
import os
import sys

# Set environment variables BEFORE any imports - this MUST be at the very top
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test_db"
os.environ["SECRET_KEY"] = "test_secret_key_for_unit_tests_not_for_production"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["ENVIRONMENT"] = "test"

# Insert the project root at the front of sys.path
sys.path.insert(0, os.path.dirname(__file__))


def pytest_configure(config):
    """
    Pytest hook that runs after command line options have been parsed
    and before test collection.
    
    Clear any cached settings to ensure environment variables are read fresh.
    """
    # Clear the settings cache so it picks up our test environment variables
    from shared.core_functions.config import get_settings
    get_settings.cache_clear()
