"""
Tests for PARWA Tenant Auto-Injection (Day 20)

Tests SQLAlchemy before_flush auto-injection of company_id,
bypass_tenant decorator, TenantSession, and get_tenant_db.
"""

import os

os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test_secret_key"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["JWT_SECRET_KEY"] = "test_jwt_key"
os.environ["DATA_ENCRYPTION_KEY"] = "12345678901234567890123456789012"

import pytest  # noqa: E402
from sqlalchemy import Column, Integer, String  # noqa: E402

from database.base import Base, TenantSession, bypass_tenant  # noqa: E402
from backend.app.core.tenant_context import (  # noqa: E402
    set_tenant_context,
    clear_tenant_context,
    reset_tenant_context,
    tenant_bypass,
)


@pytest.fixture(autouse=True)
def _reset():
    reset_tenant_context()
    yield
    reset_tenant_context()


# ── Test Models ──────────────────────────────────────────


class _TenantModel(Base):
    """Model with company_id column (auto-injectable)."""
    __tablename__ = "test_tenant_model"
    __table_args__ = {"extend_existing": True}
    id = Column(Integer, primary_key=True)
    name = Column(String(50))
    company_id = Column(String(128))


class _NoCompanyModel(Base):
    """Model without company_id (not auto-injectable)."""
    __tablename__ = "test_no_company_model"
    __table_args__ = {"extend_existing": True}
    id = Column(Integer, primary_key=True)
    name = Column(String(50))


# ── Auto-Injection ───────────────────────────────────────


class TestAutoInjection:
    """Test company_id auto-injection on flush."""

    def test_auto_inject_on_flush(self):
        """Company_id is auto-injected when flushing new object."""
        set_tenant_context("acme")
        session = TenantSession()
        try:
            Base.metadata.create_all(bind=session.bind)
            obj = _TenantModel(name="test")
            session.add(obj)
            session.flush()
            assert obj.company_id == "acme"
        finally:
            session.rollback()
            session.close()

    def test_preserves_explicit_company_id(self):
        """Explicitly set company_id is not overwritten."""
        set_tenant_context("acme")
        session = TenantSession()
        try:
            Base.metadata.create_all(bind=session.bind)
            obj = _TenantModel(name="test", company_id="explicit")
            session.add(obj)
            session.flush()
            assert obj.company_id == "explicit"
        finally:
            session.rollback()
            session.close()

    def test_skips_object_without_company_id(self):
        """Objects without company_id column are not affected."""
        set_tenant_context("acme")
        session = TenantSession()
        try:
            Base.metadata.create_all(bind=session.bind)
            obj = _NoCompanyModel(name="test")
            session.add(obj)
            session.flush()
            assert obj.name == "test"
        finally:
            session.rollback()
            session.close()

    def test_multiple_objects(self):
        """Multiple new objects all get company_id."""
        set_tenant_context("globex")
        session = TenantSession()
        try:
            Base.metadata.create_all(bind=session.bind)
            objs = [_TenantModel(name=f"item{i}") for i in range(3)]
            for o in objs:
                session.add(o)
            session.flush()
            for o in objs:
                assert o.company_id == "globex"
        finally:
            session.rollback()
            session.close()

    def test_different_contexts(self):
        """Different tenant contexts inject different company_ids."""
        set_tenant_context("tenant-a")
        s1 = TenantSession()
        try:
            Base.metadata.create_all(bind=s1.bind)
            o1 = _TenantModel(name="a")
            s1.add(o1)
            s1.flush()
            assert o1.company_id == "tenant-a"
        finally:
            s1.rollback()
            s1.close()

        set_tenant_context("tenant-b")
        s2 = TenantSession()
        try:
            o2 = _TenantModel(name="b")
            s2.add(o2)
            s2.flush()
            assert o2.company_id == "tenant-b"
        finally:
            s2.rollback()
            s2.close()


# ── Bypass ───────────────────────────────────────────────


class TestBypassTenant:

    def test_bypass_cm_skips_injection(self):
        """tenant_bypass context manager skips auto-injection."""
        with tenant_bypass(reason="admin query"):
            session = TenantSession()
            try:
                Base.metadata.create_all(bind=session.bind)
                obj = _TenantModel(name="test")
                session.add(obj)
                session.flush()
                assert obj.company_id is None
            finally:
                session.rollback()
                session.close()

    def test_bypass_decorator_sync(self):
        """@bypass_tenant decorator skips auto-injection."""
        result = {}

        @bypass_tenant(reason="test")
        def create_without_tenant():
            session = TenantSession()
            try:
                Base.metadata.create_all(bind=session.bind)
                obj = _TenantModel(name="decorated")
                session.add(obj)
                session.flush()
                result["company_id"] = obj.company_id
            finally:
                session.rollback()
                session.close()

        create_without_tenant()
        assert result["company_id"] is None

    def test_bypass_decorator_with_parens(self):
        """@bypass_tenant(reason=...) works with parentheses."""
        result = {}

        @bypass_tenant(reason="test paren")
        def create_bypass():
            session = TenantSession()
            try:
                Base.metadata.create_all(bind=session.bind)
                obj = _TenantModel(name="paren")
                session.add(obj)
                session.flush()
                result["company_id"] = obj.company_id
            finally:
                session.rollback()
                session.close()

        create_bypass()
        assert result["company_id"] is None

    def test_bypass_restores_after_context(self):
        """After bypass context exits, injection works again."""
        with tenant_bypass(reason="temporary"):
            pass

        set_tenant_context("restored")
        session = TenantSession()
        try:
            Base.metadata.create_all(bind=session.bind)
            obj = _TenantModel(name="restored")
            session.add(obj)
            session.flush()
            assert obj.company_id == "restored"
        finally:
            session.rollback()
            session.close()


# ── TenantSession ────────────────────────────────────────


class TestTenantSessionCM:

    def test_context_manager_commits(self):
        """TenantSession context manager commits on success."""
        set_tenant_context("cm-test")
        session = TenantSession()
        try:
            Base.metadata.create_all(bind=session.bind)
            with TenantSession() as session:
                obj = _TenantModel(name="cm-test")
                session.add(obj)
            with TenantSession() as check:
                result = check.query(_TenantModel).first()
                assert result is not None
                assert result.company_id == "cm-test"
        finally:
            session.close()

    def test_context_manager_rollback_on_error(self):
        """TenantSession context manager rolls back on exception."""
        set_tenant_context("err-test")
        session = TenantSession()
        try:
            Base.metadata.create_all(bind=session.bind)
            with pytest.raises(ValueError):
                with TenantSession() as session:
                    obj = _TenantModel(name="err")
                    session.add(obj)
                    raise ValueError("forced")
        finally:
            session.close()


# ── Warning Tests ────────────────────────────────────────


class TestNoContextWarning:

    def test_warning_without_context(self, caplog):
        """Flushing without context logs warning."""
        import logging
        session = TenantSession()
        try:
            Base.metadata.create_all(bind=session.bind)
            with caplog.at_level(logging.WARNING, logger="parwa.database"):
                obj = _TenantModel(name="no-ctx")
                session.add(obj)
                session.flush()
        finally:
            session.rollback()
            session.close()
        assert any(
            "auto_inject_no_tenant_context" in r.message
            for r in caplog.records
        )
