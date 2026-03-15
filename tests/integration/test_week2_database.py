"""
Integration tests for Week 2: Database and Utilities.
Verifies that the database connects, migrations run, seeds load, and Redis is accessible.

Note: These tests require actual database and Redis connections.
They will be skipped if the services are not available (e.g., in CI without services).
"""
import pytest
import os
import socket
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from backend.app.database import check_db_connection
from shared.utils.cache import Cache
from shared.utils.monitoring import init_monitoring
from shared.core_functions.config import get_settings


def _can_connect_to_host(host: str, port: int, timeout: float = 1.0) -> bool:
    """Check if we can connect to a host:port (TCP check)."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def _is_postgres_available() -> bool:
    """Check if PostgreSQL is available by trying to connect to its port."""
    # Try localhost first
    if _can_connect_to_host("localhost", 5432):
        return True
    # Try common Docker hostnames
    if _can_connect_to_host("postgres", 5432):
        return True
    if _can_connect_to_host("db", 5432):
        return True
    return False


def _is_redis_available() -> bool:
    """Check if Redis is available by trying to connect to its port."""
    if _can_connect_to_host("localhost", 6379):
        return True
    if _can_connect_to_host("redis", 6379):
        return True
    return False


@pytest.mark.asyncio
@pytest.mark.skipif(not _is_postgres_available(), reason="PostgreSQL not available")
async def test_database_connection():
    """Verify that the database is reachable and connects correctly."""
    result = await check_db_connection()
    assert result is True, "Database connection failed"


@pytest.mark.asyncio
@pytest.mark.skipif(not _is_postgres_available(), reason="PostgreSQL not available")
async def test_migrations_and_seeds():
    """Verify that migrations have run and seed data is present."""
    # Clear the lru_cache so we get the real env-based settings,
    # not any mocked values that may have been cached by unit tests.
    get_settings.cache_clear()
    settings = get_settings()
    db_url = str(settings.database_url)
    if db_url.startswith("postgres://") or db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        
    local_engine = create_async_engine(db_url)
    try:
        # Check for tables created in migrations 001-005
        tables = ["users", "tenants", "audit_logs", "compliance_data_requests", "feature_flags"]
        async with local_engine.connect() as conn:
            for table in tables:
                result = await conn.execute(text(f"SELECT 1 FROM information_schema.tables WHERE table_name = '{table}'"))
                assert result.scalar() == 1, f"Table {table} missing"
                
            # Check for seed data
            result = await conn.execute(text("SELECT count(*) FROM users"))
            count = result.scalar()
            assert count > 0, "No seed data in users table"
    finally:
        await local_engine.dispose()


@pytest.mark.asyncio
@pytest.mark.skipif(not _is_redis_available(), reason="Redis not available")
async def test_redis_connection():
    """Verify that Redis is reachable via Cache util."""
    cache = Cache()
    try:
        # Test basic set/get
        await cache.set("test_key", "test_value", expire=10)
        value = await cache.get("test_key")
        assert value == "test_value", "Redis set/get failed"
    finally:
        await cache.close()


def test_monitoring_initialization():
    """Verify that monitoring initializes without error."""
    # init_monitoring() returns None but should not raise exceptions
    # This works even without Sentry DSN configured
    init_monitoring()


def test_storage_operations():
    """Verify that Storage utility can perform basic operations."""
    from shared.utils.storage import Storage
    
    storage = Storage(base_path="/tmp/test_parwa_storage")
    test_file = "/tmp/test_file.txt"
    with open(test_file, "w") as f:
        f.write("test content")
        
    try:
        # Test upload
        stored_path = storage.upload(test_file, "test_upload.txt")
        assert stored_path is not None
        assert os.path.exists(stored_path)
        
        # Test download
        download_path = "/tmp/downloaded_test.txt"
        success = storage.download("test_upload.txt", download_path)
        assert success is True
        assert os.path.exists(download_path)
        
        # Test delete
        success = storage.delete("test_upload.txt")
        assert success is True
        assert not os.path.exists(stored_path)
    finally:
        if os.path.exists(test_file): 
            os.remove(test_file)
        if os.path.exists("/tmp/downloaded_test.txt"): 
            os.remove("/tmp/downloaded_test.txt")


def test_utils_import_cleanly():
    """Verify all utils import without circular dependencies."""
    from shared.utils.storage import Storage
    from shared.utils.message_queue import MessageQueue
    from shared.utils.error_handlers import setup_error_handlers
    from shared.utils.compliance_helpers import redact_pii
    
    assert all([Storage, MessageQueue, setup_error_handlers, redact_pii])
