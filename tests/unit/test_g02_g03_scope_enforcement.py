"""
Tests for G02: require_scope wired into endpoints.

Tests that require_scope dependency correctly enforces scope
checks for API key auth and passes through for JWT auth.
"""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from backend.app.middleware.api_key_auth import (
    require_financial_approval,
    require_financial_approval_dep,
    require_scope,
)


class TestRequireScope:
    """Tests for G02: require_scope dependency function."""

    def _make_request(self, api_key=None):
        """Create a mock request with optional api_key on state."""
        req = MagicMock()
        if api_key is not None:
            req.state.api_key = api_key
        else:
            req.state.api_key = None
        return req

    def test_no_api_key_passes_through(self):
        """No API key (JWT auth) passes through."""
        checker = require_scope("write")
        req = self._make_request(api_key=None)
        # Should not raise
        checker(req)

    def test_write_scope_allows_write(self):
        """API key with 'write' scope passes write check."""
        checker = require_scope("write")
        req = self._make_request(api_key={
            "id": "key-1",
            "scopes": ["write"],
            "company_id": "acme",
        })
        checker(req)  # Should not raise

    def test_write_scope_allows_read(self):
        """API key with 'write' scope passes read check (hierarchy)."""
        checker = require_scope("read")
        req = self._make_request(api_key={
            "id": "key-1",
            "scopes": ["write"],
            "company_id": "acme",
        })
        checker(req)  # Should not raise

    def test_read_scope_rejects_write(self):
        """API key with only 'read' scope rejects write check."""
        checker = require_scope("write")
        req = self._make_request(api_key={
            "id": "key-1",
            "scopes": ["read"],
            "company_id": "acme",
        })
        with pytest.raises(HTTPException) as exc_info:
            checker(req)
        assert exc_info.value.status_code == 403
        assert "write" in exc_info.value.detail

    def test_admin_scope_allows_all(self):
        """API key with 'admin' scope passes all checks."""
        for scope in ["read", "write", "admin"]:
            checker = require_scope(scope)
            req = self._make_request(api_key={
                "id": "key-1",
                "scopes": ["admin"],
                "company_id": "acme",
            })
            checker(req)  # Should not raise

    def test_read_scope_rejects_admin(self):
        """API key with 'read' scope rejects admin check."""
        checker = require_scope("admin")
        req = self._make_request(api_key={
            "id": "key-1",
            "scopes": ["read"],
            "company_id": "acme",
        })
        with pytest.raises(HTTPException) as exc_info:
            checker(req)
        assert exc_info.value.status_code == 403

    def test_approval_scope_passes_approval(self):
        """API key with 'approval' scope passes approval check."""
        checker = require_scope("approval")
        req = self._make_request(api_key={
            "id": "key-1",
            "scopes": ["approval"],
            "company_id": "acme",
        })
        checker(req)  # Should not raise

    def test_admin_scope_rejects_approval(self):
        """API key with 'admin' scope rejects approval check (separate scope)."""
        checker = require_scope("approval")
        req = self._make_request(api_key={
            "id": "key-1",
            "scopes": ["admin"],
            "company_id": "acme",
        })
        with pytest.raises(HTTPException) as exc_info:
            checker(req)
        assert exc_info.value.status_code == 403

    def test_empty_scopes_rejects_read(self):
        """API key with empty scopes rejects read check."""
        checker = require_scope("read")
        req = self._make_request(api_key={
            "id": "key-1",
            "scopes": [],
            "company_id": "acme",
        })
        with pytest.raises(HTTPException) as exc_info:
            checker(req)
        assert exc_info.value.status_code == 403

    def test_read_scope_allows_read(self):
        """API key with 'read' scope passes read check."""
        checker = require_scope("read")
        req = self._make_request(api_key={
            "id": "key-1",
            "scopes": ["read"],
            "company_id": "acme",
        })
        checker(req)  # Should not raise

    def test_multi_scope_write_approval_allows_read(self):
        """API key with write+approval allows read."""
        checker = require_scope("read")
        req = self._make_request(api_key={
            "id": "key-1",
            "scopes": ["write", "approval"],
            "company_id": "acme",
        })
        checker(req)  # Should not raise


class TestRequireFinancialApproval:
    """Tests for G03: require_financial_approval helper."""

    def _make_request(self, api_key=None):
        req = MagicMock()
        if api_key is not None:
            req.state.api_key = api_key
        else:
            req.state.api_key = None
        return req

    def test_no_api_key_returns_false(self):
        """No API key returns False."""
        req = self._make_request(api_key=None)
        assert require_financial_approval(req) is False

    def test_write_only_returns_false(self):
        """Only 'write' scope returns False."""
        req = self._make_request(api_key={
            "scopes": ["write"],
        })
        assert require_financial_approval(req) is False

    def test_approval_only_returns_false(self):
        """Only 'approval' scope returns False."""
        req = self._make_request(api_key={
            "scopes": ["approval"],
        })
        assert require_financial_approval(req) is False

    def test_write_plus_approval_returns_true(self):
        """Both 'write' and 'approval' returns True."""
        req = self._make_request(api_key={
            "scopes": ["write", "approval"],
        })
        assert require_financial_approval(req) is True

    def test_admin_plus_approval_returns_false(self):
        """'admin' + 'approval' returns False (no 'write')."""
        req = self._make_request(api_key={
            "scopes": ["admin", "approval"],
        })
        assert require_financial_approval(req) is False

    def test_read_write_approval_returns_true(self):
        """'read' + 'write' + 'approval' returns True."""
        req = self._make_request(api_key={
            "scopes": ["read", "write", "approval"],
        })
        assert require_financial_approval(req) is True

    def test_empty_scopes_returns_false(self):
        """Empty scopes returns False."""
        req = self._make_request(api_key={
            "scopes": [],
        })
        assert require_financial_approval(req) is False


class TestRequireFinancialApprovalDep:
    """Tests for G03: require_financial_approval_dep dependency."""

    def _make_request(self, api_key=None):
        req = MagicMock()
        if api_key is not None:
            req.state.api_key = api_key
        else:
            req.state.api_key = None
        return req

    def test_no_api_key_passes_through(self):
        """No API key (JWT auth) passes through."""
        req = self._make_request(api_key=None)
        require_financial_approval_dep(req)  # Should not raise

    def test_write_plus_approval_passes(self):
        """Both 'write' and 'approval' passes."""
        req = self._make_request(api_key={
            "scopes": ["write", "approval"],
        })
        require_financial_approval_dep(req)  # Should not raise

    def test_write_only_raises_403(self):
        """Only 'write' raises 403."""
        req = self._make_request(api_key={
            "scopes": ["write"],
        })
        with pytest.raises(HTTPException) as exc_info:
            require_financial_approval_dep(req)
        assert exc_info.value.status_code == 403
        assert "write" in exc_info.value.detail
        assert "approval" in exc_info.value.detail

    def test_approval_only_raises_403(self):
        """Only 'approval' raises 403."""
        req = self._make_request(api_key={
            "scopes": ["approval"],
        })
        with pytest.raises(HTTPException) as exc_info:
            require_financial_approval_dep(req)
        assert exc_info.value.status_code == 403

    def test_admin_only_raises_403(self):
        """Only 'admin' raises 403 (no 'write' or 'approval')."""
        req = self._make_request(api_key={
            "scopes": ["admin"],
        })
        with pytest.raises(HTTPException) as exc_info:
            require_financial_approval_dep(req)
        assert exc_info.value.status_code == 403

    def test_read_only_raises_403(self):
        """Only 'read' raises 403."""
        req = self._make_request(api_key={
            "scopes": ["read"],
        })
        with pytest.raises(HTTPException) as exc_info:
            require_financial_approval_dep(req)
        assert exc_info.value.status_code == 403

    def test_empty_scopes_raises_403(self):
        """Empty scopes raises 403."""
        req = self._make_request(api_key={
            "scopes": [],
        })
        with pytest.raises(HTTPException) as exc_info:
            require_financial_approval_dep(req)
        assert exc_info.value.status_code == 403

    def test_read_write_approval_passes(self):
        """'read' + 'write' + 'approval' passes."""
        req = self._make_request(api_key={
            "scopes": ["read", "write", "approval"],
        })
        require_financial_approval_dep(req)  # Should not raise
