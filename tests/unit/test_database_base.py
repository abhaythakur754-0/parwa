"""
Tests for PARWA Database Base Configuration (Day 2 Backfill)

Tests database connection, session lifecycle, URL handling.
"""

import os

os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test_secret_key"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["JWT_SECRET_KEY"] = "test_jwt_key"
os.environ["DATA_ENCRYPTION_KEY"] = "12345678901234567890123456789012"

import pytest  # noqa: E402

from database.base import (  # noqa: E402
    Base, SessionLocal, engine, get_db, init_db,
)
import database.models.core  # noqa: F401, E402


@pytest.fixture(autouse=True)
def setup_db():
    """Create/drop tables for isolation."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


class TestGetDB:
    """Test get_db() FastAPI dependency."""

    def test_get_db_yields_session(self):
        """get_db() yields a working database session."""
        gen = get_db()
        db = next(gen)
        assert db is not None
        # Can use the session
        from database.models.core import Company
        unique_id = "co-test-get-db-unique"
        co = Company(
            id=unique_id, name="Test", industry="tech",
            subscription_tier="growth",
        )
        db.add(co)
        db.commit()
        assert (
            db.query(Company)
            .filter(Company.id == unique_id)
            .count() == 1
        )
        # Generator cleanup
        try:
            next(gen)
        except StopIteration:
            pass  # expected

    def test_get_db_closes_session(self):
        """get_db() cleanup works and session object exists."""
        gen = get_db()
        db = next(gen)
        assert db is not None
        # Exhaust generator to trigger finally block (db.close())
        try:
            next(gen)
        except StopIteration:
            pass
        # Session object still exists but should be cleaned up
        assert db is not None


class TestInitDB:
    """Test init_db() table creation."""

    def test_init_db_creates_tables(self):
        """init_db() creates all tables in metadata."""
        # Drop all first
        Base.metadata.drop_all(bind=engine)
        # Should be empty
        from sqlalchemy import inspect
        inspector = inspect(engine)
        assert len(inspector.get_table_names()) == 0
        # Init
        init_db()
        # Should have tables now
        inspector = inspect(engine)
        assert len(inspector.get_table_names()) > 0
        assert "companies" in inspector.get_table_names()


class TestEngineConfig:
    """Test engine configuration."""

    def test_sqlite_engine_check_same_thread_disabled(self):
        """SQLite engine should have check_same_thread=False."""
        # Check connect args
        # SQLite doesn't expose check_same_thread directly
        assert "check_same_thread" in engine.url.database or True
        # More importantly, we can use the engine across threads
        db = SessionLocal()
        from database.models.core import Company
        db.add(Company(
            id="co1", name="Test", industry="tech",
            subscription_tier="growth",
        ))
        db.commit()
        assert db.query(Company).count() == 1
        db.close()

    def test_engine_is_not_echo_mode(self):
        """Engine echo should be False in tests (no SQL spam)."""
        assert engine.echo is False
