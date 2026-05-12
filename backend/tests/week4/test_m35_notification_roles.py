"""
Week 4 — M-35: Notification send + template mutation require owner/admin role.

Source code verification + functional dependency tests.
"""
import os
import inspect


class TestM35SourceCodeVerification:
    """Verify the fix exists in source code (no deep imports)."""

    def _read_notifications_py(self):
        path = "/home/z/my-project/backend/app/api/notifications.py"
        with open(path) as f:
            return f.read()

    def test_send_endpoint_has_role_check(self):
        """POST /send must use require_roles."""
        src = self._read_notifications_py()
        send_section = src[src.index("def send_notification"):]
        assert 'require_roles("owner", "admin")' in send_section, (
            "send_notification must use require_roles('owner', 'admin')"
        )

    def test_create_template_has_role_check(self):
        """POST /templates must use require_roles."""
        src = self._read_notifications_py()
        create_section = src[src.index("def create_template"):]
        assert 'require_roles("owner", "admin")' in create_section, (
            "create_template must use require_roles('owner', 'admin')"
        )

    def test_update_template_has_role_check(self):
        """PUT /templates/{id} must use require_roles."""
        src = self._read_notifications_py()
        update_section = src[src.index("def update_template"):]
        assert 'require_roles("owner", "admin")' in update_section, (
            "update_template must use require_roles('owner', 'admin')"
        )

    def test_delete_template_has_role_check(self):
        """DELETE /templates/{id} must use require_roles."""
        src = self._read_notifications_py()
        delete_section = src[src.index("def delete_template"):]
        assert 'require_roles("owner", "admin")' in delete_section, (
            "delete_template must use require_roles('owner', 'admin')"
        )

    def test_list_templates_no_role_check(self):
        """GET /templates must NOT use require_roles (accessible to all)."""
        src = self._read_notifications_py()
        list_section = src[src.index("def list_templates"):src.index("def create_template")]
        assert "require_roles" not in list_section, (
            "list_templates should NOT have role restriction"
        )

    def test_list_notifications_no_role_check(self):
        """GET /notifications must NOT use require_roles (accessible to all)."""
        src = self._read_notifications_py()
        list_section = src[src.index("def list_notifications"):src.index("def get_unread_count")]
        assert "require_roles" not in list_section, (
            "list_notifications should NOT have role restriction"
        )

    def test_m35_comment_present(self):
        """Source code must reference M-35 for traceability."""
        src = self._read_notifications_py()
        assert "M-35" in src, "M-35 comment must be present"

    def test_require_roles_imported(self):
        """notifications.py must import require_roles from deps."""
        src = self._read_notifications_py()
        assert "require_roles" in src, (
            "require_roles must be imported from app.api.deps"
        )
