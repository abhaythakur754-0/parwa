"""
Tests for BUG-3 Route Prefix Fix.

Validates that tickets_router and technique_config_router are properly
imported and mounted in main.py with correct route prefixes.
"""

import importlib
import os
from unittest.mock import MagicMock, patch

import pytest


# ── Import main.py safely by mocking heavy dependencies ─────────────


def _import_main():
    """Import main.py with heavy dependencies mocked."""
    # Ensure test environment
    if not os.environ.get("ENVIRONMENT"):
        os.environ["ENVIRONMENT"] = "test"
    if not os.environ.get("SECRET_KEY"):
        os.environ["SECRET_KEY"] = "test-secret-key-32charsXXXXXXXXX"
    if not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = "sqlite:///test.db"
    if not os.environ.get("JWT_SECRET_KEY"):
        os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-32charsXXXXX"
    if not os.environ.get("DATA_ENCRYPTION_KEY"):
        os.environ["DATA_ENCRYPTION_KEY"] = "test-encryption-key-for-testing-32"

    # Mock problematic modules before importing main
    import sys
    import types

    # Mock Socket.io if not available
    for mod_name in [
        "socketio",
        "engineio",
        "celery",
        "celery_app",
        "app.core.socketio",
    ]:
        if mod_name not in sys.modules:
            sys.modules[mod_name] = MagicMock()

    # Mock database if not set up
    for mod_name in ["database", "database.base", "database.models", "database.models.core"]:
        if mod_name not in sys.modules:
            sys.modules[mod_name] = MagicMock()

    # Import the source code of main.py as text to verify imports
    main_path = "/home/z/my-project/backend/app/main.py"
    with open(main_path, "r") as f:
        source = f.read()

    return source


class TestRoutePrefixFix:
    """Test BUG-3 route prefix fix: tickets_router and technique_config_router."""

    def test_tickets_router_imported_in_main(self):
        """tickets_router should be imported in main.py."""
        source = _import_main()
        assert "from app.api.tickets import router as tickets_router" in source, (
            "tickets_router import missing from main.py"
        )

    def test_technique_config_router_imported_in_main(self):
        """technique_config_router should be imported in main.py."""
        source = _import_main()
        assert "from app.api.technique_config import router as technique_config_router" in source, (
            "technique_config_router import missing from main.py"
        )

    def test_tickets_router_mounted_with_prefix(self):
        """tickets_router should be mounted with /api/v1 prefix."""
        source = _import_main()
        assert "tickets_router, prefix=\"/api/v1\"" in source, (
            "tickets_router should be mounted with prefix=\"/api/v1\""
        )

    def test_technique_config_router_mounted(self):
        """technique_config_router should be mounted (include_router)."""
        source = _import_main()
        assert "include_router(technique_config_router" in source, (
            "technique_config_router should be included via include_router"
        )

    def test_tickets_router_has_tags(self):
        """tickets_router mount should have tags=['tickets']."""
        source = _import_main()
        assert "tags=[\"tickets\"]" in source, (
            "tickets_router should have tags=['tickets']"
        )

    def test_technique_config_router_has_tags(self):
        """technique_config_router mount should have tags=['technique-config']."""
        source = _import_main()
        assert "tags=[\"technique-config\"]" in source, (
            "technique_config_router should have tags=['technique-config']"
        )

    def test_tickets_comment_references_bug_fix(self):
        """The tickets_router mount should have a BUG-3 FIX comment."""
        source = _import_main()
        assert "BUG-3" in source, (
            "BUG-3 FIX comment should reference the fix"
        )

    def test_technique_config_comment_references_bug_fix(self):
        """The technique_config_router mount should have a BUG-3 FIX comment."""
        source = _import_main()
        # Both imports and mount should reference the fix
        bug3_count = source.count("BUG-3")
        assert bug3_count >= 2, (
            "BUG-3 FIX should be referenced at least twice (import + mount)"
        )

    def test_no_double_mounting_tickets(self):
        """tickets_router should not be mounted twice."""
        source = _import_main()
        count = source.count("include_router(tickets_router")
        assert count == 1, (
            f"tickets_router should be mounted exactly once, found {count}"
        )

    def test_no_double_mounting_technique_config(self):
        """technique_config_router should not be mounted twice."""
        source = _import_main()
        count = source.count("include_router(technique_config_router")
        assert count == 1, (
            f"technique_config_router should be mounted exactly once, found {count}"
        )
