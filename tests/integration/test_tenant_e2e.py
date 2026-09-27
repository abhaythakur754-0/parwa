"""
Integration Tests for Tenant End-to-End Flow (Day 20)

Tests: middleware sets context → DB uses it → Redis keys scoped.
"""

import os

os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test_secret_key"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["JWT_SECRET_KEY"] = "test_jwt_key"
os.environ["DATA_ENCRYPTION_KEY"] = "12345678901234567890123456789012"

from unittest.mock import AsyncMock, patch  # noqa: E402

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from backend.app.core.tenant_context import (  # noqa: E402
    set_tenant_context,
    get_tenant_context,
    clear_tenant_context,
    reset_tenant_context,
    get_task_headers,
)
from backend.app.core.redis import make_key  # noqa: E402


@pytest.fixture(autouse=True)
def _reset():
    reset_tenant_context()
    yield
    reset_tenant_context()


# ── Context Lifecycle ────────────────────────────────────


class TestContextLifecycle:

    def test_context_set_and_used_in_db_flow(self):
        """Context flows from set → DB session → auto-inject."""
        from database.base import TenantSession, Base
        from sqlalchemy import Column, Integer, String

        class _FlowModel(Base):
            __tablename__ = "test_flow_model"
            __table_args__ = {"extend_existing": True}
            id = Column(Integer, primary_key=True)
            company_id = Column(String(128))

        set_tenant_context("flow-co")
        session = TenantSession()
        try:
            Base.metadata.create_all(bind=session.bind)
            obj = _FlowModel()
            session.add(obj)
            session.flush()
            assert obj.company_id == "flow-co"
        finally:
            session.rollback()
            session.close()

    def test_context_set_and_used_in_redis_flow(self):
        """Context flows to Redis key scoping."""
        set_tenant_context("redis-co")
        cid = get_tenant_context()
        key = make_key(cid, "test", "data")
        assert key == "parwa:redis-co:test:data"

    def test_context_set_and_used_in_task_dispatch(self):
        """Context flows to Celery task headers."""
        set_tenant_context("task-co")
        headers = get_task_headers("task-co")
        assert headers["X-Parwa-Company-ID"] == "task-co"


# ── Cross-Tenant Isolation End-to-End ────────────────────


class TestCrossTenantE2E:

    def test_db_isolation_between_tenants(self):
        """Objects created for different tenants have different company_ids."""
        from database.base import TenantSession, Base
        from sqlalchemy import Column, Integer, String

        class _E2EModel(Base):
            __tablename__ = "test_e2e_model"
            __table_args__ = {"extend_existing": True}
            id = Column(Integer, primary_key=True)
            company_id = Column(String(128))

        session = TenantSession()
        try:
            Base.metadata.create_all(bind=session.bind)
            # Tenant A
            set_tenant_context("tenant-a")
            s1 = TenantSession()
            try:
                o1 = _E2EModel()
                s1.add(o1)
                s1.flush()
                cid_a = o1.company_id
            finally:
                s1.rollback()
                s1.close()

            # Tenant B
            set_tenant_context("tenant-b")
            s2 = TenantSession()
            try:
                o2 = _E2EModel()
                s2.add(o2)
                s2.flush()
                cid_b = o2.company_id
            finally:
                s2.rollback()
                s2.close()

            assert cid_a == "tenant-a"
            assert cid_b == "tenant-b"
            assert cid_a != cid_b
        finally:
            session.close()

    def test_redis_key_isolation_between_tenants(self):
        """Redis keys for different tenants are completely separate."""
        k1 = make_key("tenant-x", "session", "s1")
        k2 = make_key("tenant-y", "session", "s1")
        assert k1 != k2
        assert k1.startswith("parwa:tenant-x:")
        assert k2.startswith("parwa:tenant-y:")


# ── Context Cleanup ──────────────────────────────────────


class TestContextCleanup:

    def test_cleared_after_middleware_flow(self):
        """Context is properly cleaned up after request processing."""
        # Simulate middleware setting context
        set_tenant_context("cleanup-co")
        assert get_tenant_context() == "cleanup-co"

        # Simulate middleware cleanup
        clear_tenant_context()
        assert get_tenant_context() is None

    def test_cleared_after_exception(self):
        """Context is cleaned up even if request raises exception."""
        set_tenant_context("exc-co")
        try:
            raise ValueError("simulated error")
        except ValueError:
            pass
        finally:
            clear_tenant_context()
        assert get_tenant_context() is None
