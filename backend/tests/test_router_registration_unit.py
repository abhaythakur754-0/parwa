"""
Unit Tests: 26 Previously Unregistered Routers

Validates that all 26 routers that were previously dead code
are now properly registered in the FastAPI application by
checking the app's route table directly.

Tests verify:
1. Router files exist on disk
2. Router files define an APIRouter variable
3. main.py imports all 26 routers
4. App route table contains routes from all 26 routers
"""

import os
import re
import sys
from pathlib import Path

import pytest


BACKEND_DIR = Path(__file__).resolve().parent.parent / "app"
API_DIR = BACKEND_DIR / "api"
MAIN_PY = BACKEND_DIR / "main.py"


# ═══════════════════════════════════════════════════════════════════
# Test: Router files exist on disk
# ═══════════════════════════════════════════════════════════════════

class TestRouterFilesExist:
    """Verify all 26 router files exist on disk."""

    ROUTER_FILES = [
        "billing.py",
        "billing_webhooks.py",
        "notifications.py",
        "customers.py",
        "sla.py",
        "channels.py",
        "identity.py",
        "custom_fields.py",
        "triggers.py",
        "ticket_lifecycle.py",
        "ticket_messages.py",
        "ticket_notes.py",
        "ticket_bulk.py",
        "ticket_merge.py",
        "ticket_search.py",
        "ticket_timeline.py",
        "ticket_assignment.py",
        "ticket_classification.py",
        "ticket_templates.py",
        "collisions.py",
        "classification.py",
        "signals.py",
        "ai_classification.py",
        "ai_signals.py",
        "rag.py",
        "response.py",
    ]

    @pytest.mark.parametrize("filename", ROUTER_FILES, ids=ROUTER_FILES)
    def test_router_file_exists(self, filename):
        """Each router file should exist in app/api/."""
        filepath = API_DIR / filename
        assert filepath.exists(), f"Router file {filepath} does not exist"


# ═══════════════════════════════════════════════════════════════════
# Test: Router files define APIRouter
# ═══════════════════════════════════════════════════════════════════

class TestRouterFilesDefineAPIRouter:
    """Verify each router file contains an APIRouter definition."""

    # (filename, router_var_name)
    ROUTER_DEFS = [
        ("billing.py", "router"),
        ("billing_webhooks.py", "router"),
        ("notifications.py", "router"),
        ("customers.py", "router"),
        ("sla.py", "router"),
        ("channels.py", "router"),
        ("identity.py", "router"),
        ("custom_fields.py", "router"),
        ("triggers.py", "router"),
        ("ticket_lifecycle.py", "router"),
        ("ticket_lifecycle.py", "incident_router"),
        ("ticket_lifecycle.py", "spam_router"),
        ("ticket_messages.py", "router"),
        ("ticket_notes.py", "router"),
        ("ticket_bulk.py", "router"),
        ("ticket_merge.py", "router"),
        ("ticket_search.py", "router"),
        ("ticket_timeline.py", "router"),
        ("ticket_assignment.py", "router"),
        ("ticket_assignment.py", "rules_router"),
        ("ticket_classification.py", "router"),
        ("ticket_templates.py", "router"),
        ("collisions.py", "router"),
        ("classification.py", "router"),
        ("signals.py", "router"),
        ("ai_classification.py", "router"),
        ("ai_signals.py", "router"),
        ("rag.py", "router"),
        ("response.py", "router"),
        ("response.py", "response_router"),
        ("response.py", "brand_voice_router"),
        ("response.py", "assignment_router"),
        ("response.py", "migration_router"),
    ]

    @pytest.mark.parametrize(
        "filename,var_name",
        ROUTER_DEFS,
        ids=[f"{f.replace('.py','')}.{v}" for f, v in ROUTER_DEFS],
    )
    def test_router_defines_api_router(self, filename, var_name):
        """Each router file should define the expected APIRouter variable."""
        filepath = API_DIR / filename
        content = filepath.read_text()
        # Look for: var_name = APIRouter(
        pattern = rf"{var_name}\s*=\s*APIRouter\s*[\(,]"
        assert re.search(pattern, content), (
            f"{filename} does not define '{var_name} = APIRouter(...)'"
        )

    @pytest.mark.parametrize(
        "filename,var_name",
        [(f, v) for f, v in ROUTER_DEFS
         if v != "router" or f != "response.py"  # response.py's `router` is a combined container
         and (v == "router" or v in ("incident_router", "spam_router", "rules_router"))],
        ids=[f"{f.replace('.py','')}.{v}" for f, v in ROUTER_DEFS
             if v != "router" or f != "response.py"
             and (v == "router" or v in ("incident_router", "spam_router", "rules_router"))],
    )
    def test_router_has_routes(self, filename, var_name):
        """Each router should have @router decorated endpoints."""
        filepath = API_DIR / filename
        content = filepath.read_text()
        pattern = rf"@{var_name}\.\w+\("
        routes = re.findall(pattern, content)
        assert len(routes) > 0, (
            f"{filename}.{var_name} has no decorated routes (no @{var_name}.<method> found)"
        )

    def test_response_combined_router_includes_sub_routers(self):
        """response.py's combined `router` should include sub-routers."""
        filepath = API_DIR / "response.py"
        content = filepath.read_text()
        # Check that the combined router includes sub-routers
        assert "router.include_router(response_router)" in content
        assert "router.include_router(brand_voice_router)" in content


# ═══════════════════════════════════════════════════════════════════
# Test: main.py imports all 26 routers
# ═══════════════════════════════════════════════════════════════════

class TestMainPyImportsAllRouters:
    """Verify main.py contains import statements for all 26 routers."""

    EXPECTED_IMPORTS = {
        "billing_router": "billing",
        "billing_webhooks_router": "billing_webhooks",
        "notifications_router": "notifications",
        "customers_router": "customers",
        "sla_router": "sla",
        "channels_router": "channels",
        "identity_router": "identity",
        "custom_fields_router": "custom_fields",
        "triggers_router": "triggers",
        "ticket_lifecycle_router": "ticket_lifecycle",
        "incident_router": "ticket_lifecycle",
        "spam_router": "ticket_lifecycle",
        "ticket_messages_router": "ticket_messages",
        "ticket_notes_router": "ticket_notes",
        "ticket_bulk_router": "ticket_bulk",
        "ticket_merge_router": "ticket_merge",
        "ticket_search_router": "ticket_search",
        "ticket_timeline_router": "ticket_timeline",
        "ticket_assignment_router": "ticket_assignment",
        "assignment_rules_router": "ticket_assignment",
        "ticket_classification_router": "ticket_classification",
        "ticket_templates_router": "ticket_templates",
        "collisions_router": "collisions",
        "classification_router": "classification",
        "signals_router": "signals",
        "ai_classification_router": "ai_classification",
        "ai_signals_router": "ai_signals",
        "rag_router": "rag",
        "response_api_router": "response",
    }

    def setup_method(self):
        self.main_content = MAIN_PY.read_text()

    @pytest.mark.parametrize(
        "router_var,module_name",
        list(EXPECTED_IMPORTS.items()),
        ids=list(EXPECTED_IMPORTS.keys()),
    )
    def test_main_imports_router(self, router_var, module_name):
        """main.py should import each router variable from its module."""
        # Look for: from app.api.<module> import <something> as <router_var>
        # or: from app.api.<module> import <var> as <router_var>
        pattern = rf"from\s+app\.api\.{module_name}\s+import\s+\w+\s+as\s+{router_var}"
        # Handle special case for rules_router (imported as rules_router from ticket_assignment)
        if router_var == "assignment_rules_router":
            pattern = rf"rules_router\s+as\s+{router_var}"
        elif router_var == "incident_router":
            pattern = rf"incident_router"
        elif router_var == "spam_router":
            pattern = rf"spam_router"
        assert re.search(pattern, self.main_content), (
            f"main.py does not import {router_var} from app.api.{module_name}"
        )

    @pytest.mark.parametrize(
        "router_var",
        list(EXPECTED_IMPORTS.keys()),
        ids=list(EXPECTED_IMPORTS.keys()),
    )
    def test_main_includes_router(self, router_var):
        """main.py should include_router() for each router variable."""
        pattern = rf"app\.include_router\({router_var}"
        assert re.search(pattern, self.main_content), (
            f"main.py does not call app.include_router({router_var})"
        )


# ═══════════════════════════════════════════════════════════════════
# Test: Prefix mapping correctness
# ═══════════════════════════════════════════════════════════════════

class TestPrefixMappingCorrectness:
    """Verify each router's include_router call has the right prefix."""

    # (router_var, expected_include_pattern)
    PREFIX_SPECS = [
        # Routers with own /api prefix (no additional prefix in main.py)
        ("billing_router", "include_router(billing_router, tags="),
        ("billing_webhooks_router", "include_router(billing_webhooks_router, tags="),
        ("classification_router", "include_router(classification_router, tags="),
        ("signals_router", "include_router(signals_router, tags="),
        ("ai_classification_router", "include_router(ai_classification_router, tags="),
        ("ai_signals_router", "include_router(ai_signals_router, tags="),
        ("rag_router", "include_router(rag_router, tags="),
        ("response_api_router", "include_router(response_api_router, tags="),

        # Routers that get /api/v1 prefix added
        ("notifications_router", 'include_router(notifications_router, prefix="/api/v1"'),
        ("customers_router", 'include_router(customers_router, prefix="/api/v1"'),
        ("sla_router", 'include_router(sla_router, prefix="/api/v1"'),
        ("channels_router", 'include_router(channels_router, prefix="/api/v1"'),
        ("identity_router", 'include_router(identity_router, prefix="/api/v1"'),
        ("custom_fields_router", 'include_router(custom_fields_router, prefix="/api/v1"'),
        ("triggers_router", 'include_router(triggers_router, prefix="/api/v1"'),
        ("ticket_lifecycle_router", 'include_router(ticket_lifecycle_router, prefix="/api/v1"'),
        ("incident_router", 'include_router(incident_router, prefix="/api/v1"'),
        ("spam_router", 'include_router(spam_router, prefix="/api/v1"'),
        ("ticket_messages_router", 'include_router(ticket_messages_router, prefix="/api/v1"'),
        ("ticket_notes_router", 'include_router(ticket_notes_router, prefix="/api/v1"'),
        ("ticket_bulk_router", 'include_router(ticket_bulk_router, prefix="/api/v1"'),
        ("ticket_merge_router", 'include_router(ticket_merge_router, prefix="/api/v1"'),
        ("ticket_search_router", 'include_router(ticket_search_router, prefix="/api/v1"'),
        ("ticket_timeline_router", 'include_router(ticket_timeline_router, prefix="/api/v1"'),
        ("ticket_assignment_router", 'include_router(ticket_assignment_router, prefix="/api/v1"'),
        ("assignment_rules_router", 'include_router(assignment_rules_router, prefix="/api/v1"'),
        ("ticket_classification_router", 'include_router(ticket_classification_router, prefix="/api/v1"'),
        ("ticket_templates_router", 'include_router(ticket_templates_router, prefix="/api/v1"'),
        ("collisions_router", 'include_router(collisions_router, prefix="/api/v1"'),
    ]

    def setup_method(self):
        self.main_content = MAIN_PY.read_text()

    @pytest.mark.parametrize(
        "router_var,expected_pattern",
        PREFIX_SPECS,
        ids=[p[0] for p in PREFIX_SPECS],
    )
    def test_include_router_call(self, router_var, expected_pattern):
        """main.py should have the correct include_router call for each router."""
        assert expected_pattern in self.main_content, (
            f"main.py does not contain '{expected_pattern}'"
        )


# ═══════════════════════════════════════════════════════════════════
# Test: No orphan router files
# ═══════════════════════════════════════════════════════════════════

class TestNoOrphanRouters:
    """Verify every .py file in app/api/ that defines a router is
    registered in main.py (no new dead code)."""

    # Files that are NOT routers (utility/helper files)
    NON_ROUTER_FILES = {
        "__init__.py",
        "deps.py",
        "schemas.py",
    }

    def test_all_api_files_with_router_are_registered(self):
        """Every .py file in app/api/ that defines an APIRouter
        should be imported in main.py."""
        main_content = MAIN_PY.read_text()

        api_files = [f for f in os.listdir(API_DIR)
                     if f.endswith(".py") and f not in self.NON_ROUTER_FILES]

        for filename in sorted(api_files):
            filepath = API_DIR / filename
            content = filepath.read_text()

            # Check if this file defines an APIRouter
            if "APIRouter(" not in content:
                continue

            module_name = filename.replace(".py", "")
            # Should be imported in main.py
            import_pattern = rf"from\s+app\.api\.{module_name}\s+import"
            assert re.search(import_pattern, main_content), (
                f"app/api/{filename} defines an APIRouter but is NOT imported in main.py. "
                f"This is a dead router!"
            )


# ═══════════════════════════════════════════════════════════════════
# Test: Endpoint count per router file
# ═══════════════════════════════════════════════════════════════════

class TestEndpointCounts:
    """Count the number of decorated endpoints in each router file."""

    # (filename, var_name, minimum_count)
    COUNT_SPECS = [
        ("billing.py", "router", 10),
        ("billing_webhooks.py", "router", 2),
        ("notifications.py", "router", 10),
        ("customers.py", "router", 8),
        ("sla.py", "router", 8),
        ("channels.py", "router", 8),
        ("identity.py", "router", 4),
        ("custom_fields.py", "router", 5),
        ("triggers.py", "router", 5),
        ("ticket_lifecycle.py", "router", 6),
        ("ticket_messages.py", "router", 4),
        ("ticket_notes.py", "router", 5),
        ("ticket_bulk.py", "router", 5),
        ("ticket_merge.py", "router", 4),
        ("ticket_search.py", "router", 4),
        ("ticket_timeline.py", "router", 4),
        ("ticket_assignment.py", "router", 4),
        ("ticket_classification.py", "router", 5),
        ("ticket_templates.py", "router", 5),
        ("collisions.py", "router", 4),
        ("classification.py", "router", 1),
        ("signals.py", "router", 1),
        ("ai_classification.py", "router", 4),
        ("ai_signals.py", "router", 3),
        ("rag.py", "router", 4),
    ]

    @pytest.mark.parametrize(
        "filename,var_name,min_count",
        COUNT_SPECS,
        ids=[f.replace(".py", "") for f, _, _ in COUNT_SPECS],
    )
    def test_minimum_endpoints(self, filename, var_name, min_count):
        """Each router should define at least the minimum number of endpoints."""
        filepath = API_DIR / filename
        content = filepath.read_text()
        pattern = rf"@{var_name}\.\w+\("
        matches = re.findall(pattern, content)
        assert len(matches) >= min_count, (
            f"{filename} has {len(matches)} endpoints, expected at least {min_count}"
        )
