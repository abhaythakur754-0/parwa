"""
Tests for PARWA Tenant Context Module (Day 20)

Tests thread-local + asyncio ContextVar for tenant context propagation.
"""

import os

os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test_secret_key"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["JWT_SECRET_KEY"] = "test_jwt_key"
os.environ["DATA_ENCRYPTION_KEY"] = "12345678901234567890123456789012"

import threading  # noqa: E402
import asyncio  # noqa: E402

import pytest  # noqa: E402

from backend.app.core.tenant_context import (  # noqa: E402
    clear_tenant_context,
    get_tenant_context,
    get_task_headers,
    is_tenant_bypassed,
    requires_tenant_context,
    reset_tenant_context,
    set_tenant_bypass,
    set_tenant_context,
    tenant_bypass,
    tenant_context,
    extract_company_id_from_headers,
    TENANT_HEADER_KEY,
)


@pytest.fixture(autouse=True)
def _reset_context():
    """Reset tenant context before and after each test."""
    reset_tenant_context()
    yield
    reset_tenant_context()


# ── Basic set/get/clear ──────────────────────────────────


class TestSetTenantContext:

    def test_set_stores_value(self):
        set_tenant_context("comp_abc")
        assert get_tenant_context() == "comp_abc"

    def test_set_strips_whitespace(self):
        set_tenant_context("  comp_abc  ")
        assert get_tenant_context() == "comp_abc"

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            set_tenant_context("")

    def test_none_raises(self):
        with pytest.raises(ValueError):
            set_tenant_context(None)

    def test_overwrites(self):
        set_tenant_context("first")
        set_tenant_context("second")
        assert get_tenant_context() == "second"


class TestGetTenantContext:

    def test_none_without_set(self):
        assert get_tenant_context() is None

    def test_returns_set_value(self):
        set_tenant_context("xyz")
        assert get_tenant_context() == "xyz"


class TestClearTenantContext:

    def test_clear_removes(self):
        set_tenant_context("abc")
        clear_tenant_context()
        assert get_tenant_context() is None

    def test_clear_idempotent(self):
        clear_tenant_context()
        clear_tenant_context()
        assert get_tenant_context() is None

    def test_clear_also_clears_bypass(self):
        set_tenant_bypass(enabled=True, reason="test")
        assert is_tenant_bypassed() is True
        clear_tenant_context()
        assert is_tenant_bypassed() is False


# ── Thread isolation ─────────────────────────────────────


class TestThreadLocalIsolation:

    def test_different_threads(self):
        results = {}

        def worker(tid, cid):
            set_tenant_context(cid)
            results[tid] = get_tenant_context()

        t1 = threading.Thread(target=worker, args=(1, "comp_t1"))
        t2 = threading.Thread(target=worker, args=(2, "comp_t2"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        assert results[1] == "comp_t1"
        assert results[2] == "comp_t2"

    def test_child_does_not_affect_main(self):
        child_val = {}

        def child():
            set_tenant_context("child_comp")
            child_val["v"] = get_tenant_context()

        t = threading.Thread(target=child)
        t.start()
        t.join()
        assert get_tenant_context() is None
        assert child_val["v"] == "child_comp"


# ── Async context var ───────────────────────────────────


class TestAsyncContextVar:

    def test_basic(self):
        set_tenant_context("async_comp")
        assert get_tenant_context() == "async_comp"
        clear_tenant_context()
        assert get_tenant_context() is None

    def test_persists_across_calls(self):
        async def inner():
            return get_tenant_context()

        set_tenant_context("persist")
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(inner())
        loop.close()
        assert result == "persist"


# ── requires_tenant_context ──────────────────────────────


class TestRequiresTenantContext:

    def test_raises_without_context(self):
        with pytest.raises(RuntimeError, match="Tenant context is required"):
            with requires_tenant_context():
                pass

    def test_yields_company_id(self):
        set_tenant_context("valid")
        with requires_tenant_context() as cid:
            assert cid == "valid"

    def test_does_not_clear(self):
        set_tenant_context("keep")
        with requires_tenant_context():
            pass
        assert get_tenant_context() == "keep"

    def test_nested(self):
        set_tenant_context("nested")
        with requires_tenant_context() as outer:
            with requires_tenant_context() as inner:
                assert outer == "nested"
                assert inner == "nested"


# ── tenant_context context manager ───────────────────────


class TestTenantContextManager:

    def test_sets_and_clears(self):
        with tenant_context("mgr"):
            assert get_tenant_context() == "mgr"
        assert get_tenant_context() is None

    def test_clears_on_exception(self):
        try:
            with tenant_context("boom"):
                raise ValueError("test")
        except ValueError:
            pass
        assert get_tenant_context() is None


# ── Bypass ───────────────────────────────────────────────


class TestTenantBypass:

    def test_default_false(self):
        assert is_tenant_bypassed() is False

    def test_enable(self):
        set_tenant_bypass(enabled=True, reason="admin")
        assert is_tenant_bypassed() is True

    def test_disable(self):
        set_tenant_bypass(enabled=True, reason="test")
        set_tenant_bypass(enabled=False)
        assert is_tenant_bypassed() is False

    def test_context_manager(self):
        with tenant_bypass(reason="admin op"):
            assert is_tenant_bypassed() is True
        assert is_tenant_bypassed() is False

    def test_cm_restores_previous(self):
        set_tenant_bypass(enabled=True, reason="outer")
        with tenant_bypass(reason="inner"):
            assert is_tenant_bypassed() is True
        assert is_tenant_bypassed() is True  # restored to previous


# ── Task headers ─────────────────────────────────────────


class TestTaskHeaders:

    def test_get_task_headers(self):
        headers = get_task_headers("acme")
        assert headers[TENANT_HEADER_KEY] == "acme"

    def test_extract_from_headers(self):
        headers = get_task_headers("acme")
        cid = extract_company_id_from_headers(headers)
        assert cid == "acme"

    def test_extract_missing(self):
        assert extract_company_id_from_headers({}) is None

    def test_extract_wrong_key(self):
        assert extract_company_id_from_headers({"X-Other": "val"}) is None
