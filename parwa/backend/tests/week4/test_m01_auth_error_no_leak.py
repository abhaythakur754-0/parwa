"""
Week 4 — M-01: AuthorizationError must NOT expose internal role names.

Tests that require_roles() and require_platform_admin() return
generic errors without leaking role or permission information.
"""
import pytest
from unittest.mock import MagicMock

from app.api.deps import require_roles, require_platform_admin
from app.exceptions import AuthorizationError


class TestM01RequireRolesNoLeak:
    """Verify require_roles does not expose required_role in error details."""

    def _make_user(self, role: str = "viewer"):
        user = MagicMock()
        user.role = role
        user.company_id = "test-company"
        user.id = "user-1"
        return user

    def test_wrong_role_raises_authorization_error(self):
        """Non-matching role must raise AuthorizationError."""
        checker = require_roles("owner", "admin")
        with pytest.raises(AuthorizationError):
            checker(user=self._make_user("viewer"))

    def test_details_is_none(self):
        """Error details must be None — no internal role info leaked."""
        checker = require_roles("owner", "admin")
        with pytest.raises(AuthorizationError) as exc_info:
            checker(user=self._make_user("viewer"))
        assert exc_info.value.details is None, (
            f"details should be None, got {exc_info.value.details!r}"
        )

    def test_message_is_generic(self):
        """Error message must be generic, not enumerate roles."""
        checker = require_roles("owner", "admin")
        with pytest.raises(AuthorizationError) as exc_info:
            checker(user=self._make_user("viewer"))
        msg = exc_info.value.message
        assert "owner" not in msg.lower(), f"Role 'owner' leaked in message: {msg}"
        assert "admin" not in msg.lower(), f"Role 'admin' leaked in message: {msg}"
        assert msg == "Insufficient permissions"

    def test_correct_role_passes_through(self):
        """Matching role must return the user object."""
        checker = require_roles("owner", "admin")
        user = self._make_user("owner")
        result = checker(user=user)
        assert result is user

    def test_single_role_restriction(self):
        """Single-role restriction also hides role name."""
        checker = require_roles("admin")
        with pytest.raises(AuthorizationError) as exc_info:
            checker(user=self._make_user("agent"))
        assert exc_info.value.details is None

    def test_details_dict_not_present(self):
        """details field must not be a dict with keys like 'required_role'."""
        checker = require_roles("owner", "admin")
        with pytest.raises(AuthorizationError) as exc_info:
            checker(user=self._make_user("viewer"))
        # Must be None, not a dict
        assert not isinstance(exc_info.value.details, dict)

    def test_status_code_is_403(self):
        """AuthorizationError must have 403 status code."""
        checker = require_roles("owner", "admin")
        with pytest.raises(AuthorizationError) as exc_info:
            checker(user=self._make_user("viewer"))
        assert exc_info.value.status_code == 403


class TestM01PlatformAdminNoLeak:
    """Verify require_platform_admin does not expose permission structure."""

    def _make_admin_user(self, is_platform_admin: bool = False):
        user = MagicMock()
        user.is_platform_admin = is_platform_admin
        user.company_id = "test-company"
        user.id = "user-1"
        return user

    def test_non_admin_raises_authorization_error(self):
        """Non-platform-admin must raise AuthorizationError."""
        with pytest.raises(AuthorizationError):
            require_platform_admin(user=self._make_admin_user(False))

    def test_details_is_none(self):
        """Error details must be None — no 'required: platform_admin' leak."""
        with pytest.raises(AuthorizationError) as exc_info:
            require_platform_admin(user=self._make_admin_user(False))
        assert exc_info.value.details is None, (
            f"details should be None, got {exc_info.value.details!r}"
        )

    def test_message_is_generic(self):
        """Message must not expose 'platform_admin'."""
        with pytest.raises(AuthorizationError) as exc_info:
            require_platform_admin(user=self._make_admin_user(False))
        msg = exc_info.value.message
        assert "platform_admin" not in msg.lower(), (
            f"'platform_admin' leaked in message: {msg}"
        )
        assert msg == "Insufficient permissions"

    def test_platform_admin_passes(self):
        """Actual platform admin must pass through."""
        user = self._make_admin_user(True)
        result = require_platform_admin(user=user)
        assert result is user
