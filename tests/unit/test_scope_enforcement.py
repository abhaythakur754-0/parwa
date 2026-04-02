"""
Tests for Scope Enforcement (G02, G03)

Tests:
- require_scope with write scope (allowed)
- require_scope with read-only scope (denied)
- require_scope with admin scope (allowed)
- require_scope with approval denied (only has write)
- require_financial_approval with both scopes
- require_financial_approval missing approval
- require_financial_approval missing write
"""

import os

os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test_secret_key_for_testing_only_not_prod"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_not_prod"
os.environ["DATA_ENCRYPTION_KEY"] = "12345678901234567890123456789012"

from unittest.mock import MagicMock  # noqa: E402

import pytest  # noqa: E402
from fastapi import HTTPException  # noqa: E402

from backend.app.middleware.api_key_auth import (  # noqa: E402
    require_financial_approval,
    require_scope,
)


def _mock_request(scopes=None, has_api_key=True):
    """Create a mock request with api_key scopes."""
    req = MagicMock()
    if has_api_key and scopes is not None:
        req.state.api_key = {"scopes": scopes}
    else:
        req.state.api_key = None
    return req


class TestRequireScope:
    """Tests for require_scope dependency (G02)."""

    def test_require_scope_write_allowed(self):
        """API key with write scope can access write endpoints."""
        checker = require_scope("write")
        req = _mock_request(scopes=["write"])
        # Should not raise
        checker(req)

    def test_require_scope_write_denied(self):
        """API key with only read scope cannot access write."""
        checker = require_scope("write")
        req = _mock_request(scopes=["read"])
        with pytest.raises(HTTPException) as exc_info:
            checker(req)
        assert exc_info.value.status_code == 403

    def test_require_scope_admin_allowed(self):
        """API key with admin scope can access admin endpoints."""
        checker = require_scope("admin")
        req = _mock_request(scopes=["admin"])
        checker(req)

    def test_require_scope_approval_denied(self):
        """API key with only write scope cannot access approval."""
        checker = require_scope("approval")
        req = _mock_request(scopes=["write"])
        with pytest.raises(HTTPException) as exc_info:
            checker(req)
        assert exc_info.value.status_code == 403

    def test_require_scope_no_api_key_passes(self):
        """No API key (JWT auth) passes through without error."""
        checker = require_scope("write")
        req = _mock_request(scopes=None, has_api_key=False)
        # Should not raise — JWT users have role-based perms
        checker(req)

    def test_require_scope_empty_scopes(self):
        """Empty scopes list cannot access any scope."""
        checker = require_scope("read")
        req = _mock_request(scopes=[])
        with pytest.raises(HTTPException) as exc_info:
            checker(req)
        assert exc_info.value.status_code == 403

    def test_require_scope_admin_covers_write(self):
        """Admin scope covers write (hierarchy)."""
        checker = require_scope("write")
        req = _mock_request(scopes=["admin"])
        checker(req)

    def test_require_scope_admin_covers_read(self):
        """Admin scope covers read (hierarchy)."""
        checker = require_scope("read")
        req = _mock_request(scopes=["admin"])
        checker(req)

    def test_require_scope_write_covers_read(self):
        """Write scope covers read (hierarchy)."""
        checker = require_scope("read")
        req = _mock_request(scopes=["write"])
        checker(req)

    def test_require_scope_read_denied_admin(self):
        """Read scope cannot access admin."""
        checker = require_scope("admin")
        req = _mock_request(scopes=["read"])
        with pytest.raises(HTTPException) as exc_info:
            checker(req)
        assert exc_info.value.status_code == 403


class TestRequireFinancialApproval:
    """Tests for require_financial_approval (G03)."""

    def test_require_financial_approval_both_scopes(self):
        """Both write and approval scopes returns True."""
        req = _mock_request(
            scopes=["read", "write", "approval"]
        )
        assert require_financial_approval(req) is True

    def test_require_financial_approval_missing_approval(self):
        """Missing approval scope returns False."""
        req = _mock_request(scopes=["read", "write"])
        assert require_financial_approval(req) is False

    def test_require_financial_approval_missing_write(self):
        """Missing write scope returns False."""
        req = _mock_request(scopes=["read", "approval"])
        assert require_financial_approval(req) is False

    def test_require_financial_approval_no_api_key(self):
        """No API key returns False."""
        req = _mock_request(scopes=None, has_api_key=False)
        assert require_financial_approval(req) is False

    def test_require_financial_approval_only_approval(self):
        """Only approval scope (no write) returns False."""
        req = _mock_request(scopes=["approval"])
        assert require_financial_approval(req) is False

    def test_require_financial_approval_only_write(self):
        """Only write scope (no approval) returns False."""
        req = _mock_request(scopes=["write"])
        assert require_financial_approval(req) is False

    def test_require_financial_approval_empty_scopes(self):
        """Empty scopes returns False."""
        req = _mock_request(scopes=[])
        assert require_financial_approval(req) is False

    def test_require_financial_approval_exact_both(self):
        """Exactly write + approval (no read) returns True."""
        req = _mock_request(
            scopes=["write", "approval"]
        )
        assert require_financial_approval(req) is True
