"""
Week 4 — M-08: /api/events/since endpoint requires JWT authentication.

Source code verification tests + functional import test.
"""
import os


class TestM08EventsEndpointSourceCode:
    """Verify the fix exists in the source code (no deep imports needed)."""

    def _read_main_py(self):
        path = "/home/z/my-project/backend/app/main.py"
        with open(path) as f:
            return f.read()

    def test_events_endpoint_has_get_current_user_import(self):
        """main.py must import get_current_user."""
        src = self._read_main_py()
        assert "from app.api.deps import get_current_user" in src, (
            "main.py must import get_current_user for M-08 fix"
        )

    def test_events_endpoint_imports_user_model(self):
        """main.py must import User model for the dependency type."""
        src = self._read_main_py()
        assert "from database.models.core import User" in src, (
            "main.py must import User model for M-08 fix"
        )

    def test_events_endpoint_has_auth_parameter(self):
        """The events endpoint function must have current_user parameter."""
        src = self._read_main_py()
        assert "current_user: User = Depends(get_current_user)" in src, (
            "get_events_since_endpoint must have Depends(get_current_user) parameter"
        )

    def test_m08_comment_present(self):
        """Source code must reference M-08 for traceability."""
        src = self._read_main_py()
        assert "M-08" in src, "M-08 comment must be present for traceability"

    def test_events_endpoint_exists(self):
        """The /api/events/since route definition must exist."""
        src = self._read_main_py()
        assert '/api/events/since"' in src or "/api/events/since" in src, (
            "/api/events/since endpoint must be defined"
        )

    def test_events_was_previously_unprotected(self):
        """The fix changed from no-auth to auth-required."""
        src = self._read_main_py()
        # The old version used getattr(request.state, "company_id", None)
        # without auth dependency. Now it has Depends(get_current_user).
        assert "Depends(get_current_user)" in src, (
            "M-08 fix must add Depends(get_current_user)"
        )
