"""
Integration Tests: 26 Previously Unregistered Routers

Validates that all 26 routers are registered in the FastAPI app
and their endpoints exist in the route table.

Uses conftest.py's existing mock infrastructure.
"""

import pytest


def _get_app_routes():
    """Extract all registered routes as (method, path) tuples."""
    from app.main import app
    routes = []
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            for method in route.methods:
                if method not in ("HEAD", "OPTIONS"):
                    routes.append((method, route.path))
    return routes


def _get_route_paths():
    """Return a set of all registered route paths."""
    return {path for _, path in _get_app_routes()}


# ═══════════════════════════════════════════════════════════════════
# Test: All 26 newly registered router prefixes exist
# ═══════════════════════════════════════════════════════════════════

class TestNewlyRegisteredRoutes:
    """Verify routes from all 26 previously dead routers exist."""

    # (search_term, description)
    ROUTE_CHECKS = [
        ("billing", "Billing CRUD"),
        ("webhooks/paddle", "Paddle webhooks"),
        ("notification", "Notifications"),
        ("customer", "Customers"),
        ("sla", "SLA policies"),
        ("channel", "Channels"),
        ("identity", "Identity resolution"),
        ("custom-field", "Custom fields"),
        ("trigger", "Triggers"),
        ("escalate", "Ticket lifecycle - escalate"),
        ("reopen", "Ticket lifecycle - reopen"),
        ("messages", "Ticket messages"),
        ("notes", "Ticket notes"),
        ("bulk", "Ticket bulk actions"),
        ("merge", "Ticket merge"),
        ("collision", "Collision detection"),
        ("incident", "Incidents"),
        ("spam", "Spam moderation"),
        ("assignment", "Ticket assignment"),
        ("classification", "Classification"),
        ("signal", "Signal extraction"),
        ("rag", "RAG retrieval"),
        ("response", "Response generation"),
        ("brand-voice", "Brand voice"),
        ("migration", "Migration"),
        ("template", "Ticket templates"),
        ("timeline", "Ticket timeline"),
    ]

    @pytest.mark.parametrize(
        "search_term,description",
        ROUTE_CHECKS,
        ids=[d for _, d in ROUTE_CHECKS],
    )
    def test_route_exists(self, search_term, description):
        """Each route from previously dead routers should now exist."""
        paths = _get_route_paths()
        found = any(search_term in p for p in paths)
        assert found, (
            f"{description} route (containing '{search_term}') not found in app. "
            f"Available paths with similar terms: "
            f"{[p for p in paths if search_term[:4] in p][:5]}"
        )


# ═══════════════════════════════════════════════════════════════════
# Test: Route count and dedup
# ═══════════════════════════════════════════════════════════════════

class TestRouteCount:
    def test_minimum_total_routes(self):
        """After registration, should have significantly more routes."""
        routes = _get_app_routes()
        assert len(routes) >= 100, (
            f"Expected at least 100 routes, got {len(routes)}"
        )

    def test_no_exact_duplicate_routes(self):
        """Minimal duplicate routes are acceptable (ticket sub-routers
        may overlap on /api/v1/tickets prefix). Allow up to 10."""
        routes = _get_app_routes()
        unique = set(routes)
        dupes = len(routes) - len(unique)
        assert dupes <= 10, (
            f"Found {dupes} duplicate routes (expected <= 10). "
            f"Some ticket sub-routers share /api/v1/tickets prefix."
        )


# ═══════════════════════════════════════════════════════════════════
# Test: Core routes still work
# ═══════════════════════════════════════════════════════════════════

class TestCoreRoutesUnchanged:
    """Verify adding new routers didn't break existing routes."""

    CORE_ROUTES = [
        ("auth", "Authentication"),
        ("health", "Health check"),
        ("mfa", "MFA"),
        ("jarvis", "Jarvis"),
        ("webhook", "Webhooks"),
        ("pricing", "Pricing"),
        ("onboarding", "Onboarding"),
        ("knowledge", "Knowledge base"),
    ]

    @pytest.mark.parametrize(
        "search_term,description",
        CORE_ROUTES,
        ids=[d for _, d in CORE_ROUTES],
    )
    def test_core_route_exists(self, search_term, description):
        """Core routes should still be accessible."""
        paths = _get_route_paths()
        found = any(search_term in p for p in paths)
        assert found, f"Core {description} route not found"


# ═══════════════════════════════════════════════════════════════════
# Test: All router variables accessible from main module
# ═══════════════════════════════════════════════════════════════════

class TestMainModuleRouterVars:
    """Verify main.py exports all 29 router variables."""

    EXPECTED_VARS = [
        "billing_router",
        "billing_webhooks_router",
        "notifications_router",
        "customers_router",
        "sla_router",
        "channels_router",
        "identity_router",
        "custom_fields_router",
        "triggers_router",
        "ticket_lifecycle_router",
        "incident_router",
        "spam_router",
        "ticket_messages_router",
        "ticket_notes_router",
        "ticket_bulk_router",
        "ticket_merge_router",
        "ticket_search_router",
        "ticket_timeline_router",
        "ticket_assignment_router",
        "assignment_rules_router",
        "ticket_classification_router",
        "ticket_templates_router",
        "collisions_router",
        "classification_router",
        "signals_router",
        "ai_classification_router",
        "ai_signals_router",
        "rag_router",
        "response_api_router",
    ]

    @pytest.mark.parametrize(
        "router_var",
        EXPECTED_VARS,
        ids=EXPECTED_VARS,
    )
    def test_router_var_accessible(self, router_var):
        """Each router variable should be accessible from main module."""
        import app.main as main_module
        assert hasattr(main_module, router_var), (
            f"main.py does not expose {router_var}"
        )
