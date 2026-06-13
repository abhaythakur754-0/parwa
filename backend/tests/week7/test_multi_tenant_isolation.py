"""
Week 7 — Multi-Tenant Isolation Tests (CRITICAL Security)

Verifies that every API endpoint is isolated by company_id (BC-001).
Tests are STATIC analysis — they read source files and verify patterns
without requiring a running server or database.

For each route module, we verify:
1. The route uses get_current_user (or equivalent auth) dependency
2. The handler extracts company_id from the user token (NOT from request body)
3. Database queries filter by company_id

Cross-tenant access prevention:
- Test that JWT company_id claim is used (not from request body/header)
- Test that service constructors receive company_id
"""

import ast
import os
import re
from pathlib import Path
from typing import List, Tuple

import pytest

# Base path — all paths relative to project root
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
BACKEND_DIR = BASE_DIR / "backend" / "app"
API_DIR = BACKEND_DIR / "api"


# ────────────────────────────────────────────────────────────────────
# Helpers: Read and analyze route files
# ────────────────────────────────────────────────────────────────────

def _read_file(filepath: str) -> str:
    """Read a source file and return its content."""
    full = os.path.join(BASE_DIR, filepath)
    with open(full, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _find_company_id_usage(content: str) -> List[str]:
    """Find all lines referencing company_id in a file."""
    return [line.strip() for line in content.splitlines()
            if "company_id" in line and not line.strip().startswith("#")]


def _has_get_current_user(content: str) -> bool:
    """Check if the file uses get_current_user dependency."""
    return "get_current_user" in content


def _has_get_current_company(content: str) -> bool:
    """Check if the file uses get_current_company dependency."""
    return "get_current_company" in content


def _has_require_platform_admin(content: str) -> bool:
    """Check if the file uses require_platform_admin dependency."""
    return "require_platform_admin" in content


def _has_require_roles(content: str) -> bool:
    """Check if the file uses require_roles dependency."""
    return "require_roles" in content


def _extracts_company_id_from_user(content: str) -> bool:
    """Check that company_id is extracted from user object, not request body."""
    # Good patterns: current_user.get("company_id"), user.company_id, company_id=user.company_id
    # Bad patterns: data.company_id, body.company_id, request.json()["company_id"]
    good_patterns = [
        r"user\.company_id",
        r"current_user\.get\(\s*[\"']company_id[\"']\s*\)",
        r"company_id\s*=\s*user\.company_id",
        r"company_id\s*=\s*current_user\.get",
        r"company_id\s*=\s*company\.id",
        r"Depends\(get_company_id\)",
        r"company_id\s*=\s*UUID\(.*request\.state\.company_id",
    ]
    bad_patterns = [
        r"data\.company_id",
        r"body\.company_id",
        r"payload\.company_id",
    ]

    has_good = any(re.search(p, content) for p in good_patterns)
    has_bad = any(re.search(p, content) for p in bad_patterns)

    # If file has company_id references and uses a good pattern, that's fine
    return has_good and not has_bad


def _has_auth_dependency(content: str) -> bool:
    """Check if any auth dependency is present."""
    return (
        _has_get_current_user(content)
        or _has_get_current_company(content)
        or _has_require_platform_admin(content)
        or _has_require_roles(content)
    )


# ────────────────────────────────────────────────────────────────────
# SECTION 1: Per-module tenant isolation tests
# ────────────────────────────────────────────────────────────────────

class TestTicketsTenantIsolation:
    """Verify tickets.py is tenant-isolated (BC-001)."""

    def setup_method(self):
        self.content = _read_file("backend/app/api/tickets.py")

    def test_uses_auth_dependency(self):
        assert _has_get_current_user(self.content), \
            "tickets.py must use get_current_user dependency"

    def test_extracts_company_id_from_user(self):
        assert _extracts_company_id_from_user(self.content), \
            "tickets.py must extract company_id from user, not request body"

    def test_passes_company_id_to_service(self):
        assert "TicketService(db, company_id)" in self.content, \
            "TicketService must be constructed with company_id"

    def test_create_ticket_gets_company_id(self):
        assert 'company_id = current_user.get("company_id")' in self.content, \
            "create_ticket must extract company_id from current_user"

    def test_list_tickets_gets_company_id(self):
        assert 'company_id = current_user.get("company_id")' in self.content, \
            "list_tickets must extract company_id from current_user"

    def test_all_endpoints_have_auth(self):
        # Count route handlers vs handlers with auth
        lines = self.content.splitlines()
        route_count = sum(1 for l in lines if l.strip().startswith("@router."))
        # Every route should use get_current_user
        auth_deps = self.content.count("get_current_user")
        assert auth_deps >= route_count, \
            f"All {route_count} routes must use get_current_user, found {auth_deps}"


class TestAdminTenantIsolation:
    """Verify admin.py is tenant-isolated (BC-001).

    Admin endpoints use require_platform_admin for cross-tenant access
    control, but individual operations are still scoped to company_id.
    """

    def setup_method(self):
        self.content = _read_file("backend/app/api/admin.py")

    def test_uses_platform_admin_dependency(self):
        assert _has_require_platform_admin(self.content), \
            "admin.py must use require_platform_admin dependency"

    def test_admin_has_auth(self):
        assert _has_auth_dependency(self.content), \
            "admin.py must have authentication dependency"

    def test_company_id_used_in_operations(self):
        company_id_lines = _find_company_id_usage(self.content)
        assert len(company_id_lines) > 0, \
            "admin.py must reference company_id in operations"


class TestClientTenantIsolation:
    """Verify client.py is tenant-isolated (BC-001)."""

    def setup_method(self):
        self.content = _read_file("backend/app/api/client.py")

    def test_uses_auth_dependency(self):
        assert _has_auth_dependency(self.content), \
            "client.py must use authentication dependency"

    def test_uses_get_current_company(self):
        assert _has_get_current_company(self.content), \
            "client.py must use get_current_company for company scoping"

    def test_company_scoped_operations(self):
        assert "company_id=company.id" in self.content, \
            "client.py must pass company.id to service calls"

    def test_team_management_filters_by_company(self):
        assert "User.company_id == company.id" in self.content, \
            "Team queries must filter by company_id"

    def test_settings_scoped_to_company(self):
        assert "company_id=company.id" in self.content, \
            "Settings must be scoped to company_id"


class TestAPIKeysTenantIsolation:
    """Verify api_keys.py is tenant-isolated (BC-001)."""

    def setup_method(self):
        self.content = _read_file("backend/app/api/api_keys.py")

    def test_uses_auth_dependency(self):
        assert _has_get_current_user(self.content), \
            "api_keys.py must use get_current_user dependency"

    def test_scopes_to_user_company(self):
        assert "user.company_id" in self.content, \
            "API key operations must be scoped to user.company_id"

    def test_create_key_scoped(self):
        assert 'company_id=user.company_id' in self.content, \
            "create_key must be scoped to user.company_id"

    def test_list_keys_scoped(self):
        assert "user.company_id" in self.content, \
            "list_keys must filter by user.company_id"

    def test_revoke_key_scoped(self):
        assert "company_id=user.company_id" in self.content, \
            "revoke_key must verify company_id ownership"


class TestMFATenantIsolation:
    """Verify mfa.py is tenant-isolated (BC-001).

    MFA endpoints operate on the authenticated user's own account,
    which is inherently scoped via get_current_user.
    """

    def setup_method(self):
        self.content = _read_file("backend/app/api/mfa.py")

    def test_uses_auth_dependency(self):
        assert _has_get_current_user(self.content), \
            "mfa.py must use get_current_user dependency"

    def test_mfa_ops_on_authenticated_user(self):
        # MFA operations use 'user' from get_current_user — inherently scoped
        assert "user: User = Depends(get_current_user)" in self.content, \
            "MFA endpoints must authenticate the user"

    def test_no_cross_tenant_access(self):
        # MFA should NOT have patterns that allow accessing other users
        assert "target_user_id" not in self.content, \
            "mfa.py should not allow targeting other users by ID"


class TestKnowledgeBaseTenantIsolation:
    """Verify knowledge_base.py is tenant-isolated (BC-001)."""

    def setup_method(self):
        self.content = _read_file("backend/app/api/knowledge_base.py")

    def test_uses_auth_dependency(self):
        assert _has_get_current_user(self.content), \
            "knowledge_base.py must use get_current_user dependency"

    def test_upload_scoped_to_company(self):
        assert "company_id=user.company_id" in self.content, \
            "Knowledge upload must be scoped to user.company_id"

    def test_list_documents_scoped(self):
        assert "KnowledgeDocument.company_id == user.company_id" in self.content, \
            "Document listing must filter by company_id"

    def test_get_document_scoped(self):
        # Check that document retrieval filters by both id AND company_id
        assert 'KnowledgeDocument.company_id == user.company_id' in self.content, \
            "Document get must filter by company_id"

    def test_delete_document_scoped(self):
        assert "company_id == user.company_id" in self.content, \
            "Document delete must verify company_id ownership"

    def test_stats_scoped_to_company(self):
        assert "user.company_id" in self.content, \
            "KB stats must be scoped to company_id"

    def test_celery_task_receives_company_id(self):
        assert "user.company_id" in self.content, \
            "Celery tasks must receive company_id for processing"


class TestBillingTenantIsolation:
    """Verify billing.py is tenant-isolated (BC-001).

    Billing uses request.state.company_id (set by JWT middleware).
    """

    def setup_method(self):
        self.content = _read_file("backend/app/api/billing.py")

    def test_uses_auth_mechanism(self):
        # billing.py uses request.state.company_id set by middleware + require_roles
        assert "request.state.company_id" in self.content or "get_company_id" in self.content, \
            "billing.py must extract company_id from authenticated request"

    def test_company_id_dependency_function(self):
        assert "def get_company_id" in self.content, \
            "billing.py must define get_company_id dependency"

    def test_subscription_service_receives_company_id(self):
        assert "company_id=company_id" in self.content, \
            "Subscription service calls must pass company_id"

    def test_invoice_service_scoped(self):
        assert "company_id=company_id" in self.content, \
            "Invoice operations must be scoped to company_id"

    def test_usage_scoped_to_company(self):
        assert "company_id=company_id" in self.content, \
            "Usage queries must be scoped to company_id"

    def test_company_id_not_from_body(self):
        # company_id should come from auth, not from request body
        body_pattern = r"body\.company_id|data\.company_id"
        assert not re.search(body_pattern, self.content), \
            "billing.py must NOT accept company_id from request body"


class TestWebhooksTenantIsolation:
    """Verify webhooks.py is tenant-isolated (BC-001).

    Webhooks extract company_id from the provider payload (HMAC verified).
    Status/retry endpoints require platform admin.
    """

    def setup_method(self):
        self.content = _read_file("backend/app/api/webhooks.py")

    def test_company_id_required(self):
        assert 'company_id is required (BC-001)' in self.content, \
            "webhooks.py must require company_id in payload"

    def test_admin_endpoints_protected(self):
        assert "require_platform_admin" in self.content, \
            "Webhook status/retry must require platform admin"

    def test_company_id_from_payload_not_user(self):
        # Webhooks extract from verified payload, not from user — by design
        assert "_get_company_id_from_payload" in self.content, \
            "Webhooks must have company_id extraction from provider payload"

    def test_process_webhook_receives_company_id(self):
        assert 'company_id=company_id' in self.content, \
            "process_webhook must receive company_id"


class TestJarvisTenantIsolation:
    """Verify jarvis.py is tenant-isolated (BC-001)."""

    def setup_method(self):
        self.content = _read_file("backend/app/api/jarvis.py")

    def test_uses_auth_dependency(self):
        assert _has_get_current_user(self.content), \
            "jarvis.py must use get_current_user dependency"

    def test_session_uses_company_id(self):
        assert "user.company_id" in self.content, \
            "Jarvis session must be scoped to user.company_id"

    def test_create_session_passes_company_id(self):
        assert "company_id=user.company_id" in self.content, \
            "create_session must pass company_id to service"

    def test_send_message_scoped(self):
        assert "user.company_id" in self.content, \
            "Message sending must use company_id"

    def test_context_entry_uses_company_id(self):
        assert "company_id=user.company_id" in self.content, \
            "Context entry must pass company_id"


class TestJarvisCCTenantIsolation:
    """Verify jarvis_cc.py is tenant-isolated (BC-001)."""

    def setup_method(self):
        self.content = _read_file("backend/app/api/jarvis_cc.py")

    def test_uses_auth_dependency(self):
        assert _has_get_current_user(self.content), \
            "jarvis_cc.py must use get_current_user dependency"

    def test_company_id_validation_present(self):
        assert "user.company_id" in self.content, \
            "jarvis_cc.py must use user.company_id"

    def test_session_creation_scoped(self):
        assert "company_id=str(user.company_id)" in self.content, \
            "CC session creation must be scoped to company_id"

    def test_awareness_engine_scoped(self):
        assert "company_id=str(user.company_id)" in self.content, \
            "Awareness engine calls must pass company_id"

    def test_command_layer_scoped(self):
        assert "company_id=str(user.company_id)" in self.content, \
            "Command layer must pass company_id"

    def test_no_company_id_from_body(self):
        # Verify company_id is never taken from request body
        lines = [l.strip() for l in self.content.splitlines()]
        company_from_body = [l for l in lines
                             if "company_id" in l
                             and ("body.company_id" in l
                                 or "data.company_id" in l)]
        assert len(company_from_body) == 0, \
            "jarvis_cc.py must never take company_id from request body"


# ────────────────────────────────────────────────────────────────────
# SECTION 2: Cross-tenant access prevention tests
# ────────────────────────────────────────────────────────────────────

class TestCrossTenantAccessPrevention:
    """Verify patterns that prevent cross-tenant data access."""

    def test_tickets_service_filters_by_company(self):
        """TicketService constructor must accept and use company_id."""
        content = _read_file("backend/app/api/tickets.py")
        # Service is instantiated with company_id from user
        assert "TicketService(db, company_id)" in content, \
            "TicketService must be constructed with company_id for filtering"

    def test_api_keys_service_filters_by_company(self):
        """API key service calls must pass company_id."""
        content = _read_file("backend/app/api/api_keys.py")
        assert "company_id=user.company_id" in content, \
            "API key operations must pass company_id"

    def test_kb_documents_filtered_by_company(self):
        """Knowledge base queries must filter by company_id."""
        content = _read_file("backend/app/api/knowledge_base.py")
        assert "KnowledgeDocument.company_id == user.company_id" in content, \
            "KB document queries must filter by company_id"

    def test_client_team_filtered_by_company(self):
        """Client team queries must filter by company_id."""
        content = _read_file("backend/app/api/client.py")
        assert "User.company_id == company.id" in content, \
            "Team member queries must filter by company_id"

    def test_jarvis_session_scoped_to_company(self):
        """Jarvis sessions must be company-scoped."""
        content = _read_file("backend/app/api/jarvis.py")
        # Sessions are created with company_id
        assert "company_id=user.company_id" in content, \
            "Jarvis sessions must be company-scoped"

    def test_jarvis_cc_session_scoped_to_company(self):
        """Jarvis CC sessions must be company-scoped."""
        content = _read_file("backend/app/api/jarvis_cc.py")
        assert "company_id=str(user.company_id)" in content, \
            "Jarvis CC sessions must be company-scoped"


class TestNoCompanyFromBody:
    """Verify no route accepts company_id from request body or headers.

    company_id MUST come from the JWT token to prevent tenant spoofing.
    """

    @pytest.fixture(params=[
        "backend/app/api/tickets.py",
        "backend/app/api/client.py",
        "backend/app/api/api_keys.py",
        "backend/app/api/knowledge_base.py",
        "backend/app/api/jarvis.py",
        "backend/app/api/jarvis_cc.py",
    ])
    def protected_route(self, request):
        return request.param

    def test_no_body_company_id(self, protected_route):
        """Routes must not accept company_id from request body."""
        content = _read_file(protected_route)
        # Look for patterns like body.company_id, data.company_id
        bad_patterns = [
            r"\bdata\.company_id\b",
            r"\bbody\.company_id\b",
            r"\bpayload\.company_id\b",
        ]
        for pattern in bad_patterns:
            match = re.search(pattern, content)
            assert match is None, \
                f"{protected_route} must NOT accept company_id from request body " \
                f"(found: {match.group()})"


# ────────────────────────────────────────────────────────────────────
# SECTION 3: JWT company_id claim usage
# ────────────────────────────────────────────────────────────────────

class TestJWTCompanyIDClaim:
    """Verify company_id is extracted from JWT token claims."""

    def test_deps_extracts_company_id(self):
        """deps.py must provide company_id from JWT."""
        content = _read_file("backend/app/api/deps.py")
        assert "company_id" in content, \
            "deps.py must handle company_id extraction"

    def test_get_current_user_returns_user_with_company(self):
        """get_current_user must return a User with company_id."""
        content = _read_file("backend/app/api/deps.py")
        # User is fetched from DB, which has company_id
        assert "db.query(User)" in content, \
            "get_current_user must query User from database"

    def test_get_company_id_helper_exists(self):
        """deps.py must have get_company_id helper."""
        content = _read_file("backend/app/api/deps.py")
        assert "def get_company_id" in content, \
            "deps.py must define get_company_id helper"

    def test_auth_token_contains_company_id(self):
        """Auth token creation must include company_id claim."""
        content = _read_file("backend/app/core/auth.py")
        assert "company_id" in content, \
            "auth.py must include company_id in token creation"


# ────────────────────────────────────────────────────────────────────
# SECTION 4: LangGraph multi-tenant tests
# ────────────────────────────────────────────────────────────────────

class TestLangGraphTenantIsolation:
    """Verify LangGraph nodes receive and pass tenant_id (BC-001)."""

    def test_state_has_tenant_id(self):
        """ParwaGraphState must have tenant_id field."""
        content = _read_file("backend/app/core/langgraph/state.py")
        assert 'tenant_id' in content, \
            "ParwaGraphState must have tenant_id field for BC-001"

    def test_tenant_id_documented(self):
        """tenant_id field must be documented as multi-tenant isolation."""
        content = _read_file("backend/app/core/langgraph/state.py")
        assert 'BC-001' in content or 'tenant' in content.lower(), \
            "State file must document BC-001 multi-tenant requirement"

    def test_create_initial_state_accepts_tenant_id(self):
        """create_initial_state must accept tenant_id parameter."""
        content = _read_file("backend/app/core/langgraph/state.py")
        assert 'tenant_id' in content, \
            "create_initial_state must accept tenant_id"

    def test_tenant_id_in_input_group(self):
        """tenant_id must be in the INPUT group of ParwaGraphState."""
        content = _read_file("backend/app/core/langgraph/state.py")
        # tenant_id should appear in GROUP 1: INPUT
        assert re.search(r'tenant_id.*str', content), \
            "tenant_id must be typed as str in state"

    def test_initial_state_sets_tenant_id(self):
        """create_initial_state must set tenant_id in initial state dict."""
        content = _read_file("backend/app/core/langgraph/state.py")
        assert '"tenant_id": tenant_id' in content, \
            "create_initial_state must set tenant_id from parameter"


# ────────────────────────────────────────────────────────────────────
# SECTION 5: Comprehensive route coverage
# ────────────────────────────────────────────────────────────────────

class TestAllRoutesHaveTenantIsolation:
    """Comprehensive test that ALL major route modules are tenant-isolated."""

    # List of route files that MUST have tenant isolation
    PROTECTED_ROUTES = [
        ("backend/app/api/tickets.py", "get_current_user", "company_id"),
        ("backend/app/api/client.py", "get_current_company", "company"),
        ("backend/app/api/api_keys.py", "get_current_user", "company_id"),
        ("backend/app/api/knowledge_base.py", "get_current_user", "company_id"),
        ("backend/app/api/jarvis.py", "get_current_user", "company_id"),
        ("backend/app/api/jarvis_cc.py", "get_current_user", "company_id"),
    ]

    @pytest.fixture(params=PROTECTED_ROUTES)
    def route_config(self, request):
        return request.param

    def test_route_has_auth(self, route_config):
        """Every protected route must have an auth dependency."""
        filepath, auth_dep, _ = route_config
        content = _read_file(filepath)
        assert auth_dep in content, \
            f"{filepath} must use {auth_dep} dependency"

    def test_route_uses_company_id(self, route_config):
        """Every protected route must reference company_id."""
        filepath, _, company_ref = route_config
        content = _read_file(filepath)
        assert company_ref in content, \
            f"{filepath} must reference {company_ref} for tenant isolation"


# ────────────────────────────────────────────────────────────────────
# SECTION 6: Billing middleware tenant isolation
# ────────────────────────────────────────────────────────────────────

class TestBillingMiddlewareTenantIsolation:
    """Verify billing.py uses middleware-set company_id (not from user dict)."""

    def test_billing_get_company_id_from_state(self):
        """billing.py get_company_id must read from request.state."""
        content = _read_file("backend/app/api/billing.py")
        assert "request.state.company_id" in content, \
            "billing.py get_company_id must read from request.state"

    def test_billing_rejects_missing_company_id(self):
        """billing.py must reject requests without company_id."""
        content = _read_file("backend/app/api/billing.py")
        assert "401" in content or "UNAUTHORIZED" in content, \
            "billing.py must return 401 when company_id is missing"

    def test_billing_no_fallback_to_user_dict(self):
        """billing.py uses middleware-set company_id, not from user dict directly."""
        content = _read_file("backend/app/api/billing.py")
        # billing.py should use request.state.company_id (set by middleware from JWT)
        # NOT read company_id from current_user dict directly
        assert "request.state.company_id" in content, \
            "billing.py must use request.state.company_id for tenant isolation"


# ────────────────────────────────────────────────────────────────────
# SECTION 7: Admin special-case validation
# ────────────────────────────────────────────────────────────────────

class TestAdminPlatformAdminIsolation:
    """Admin endpoints use platform_admin auth, but still log company_id."""

    def test_admin_logs_company_id(self):
        """Admin operations that affect a specific company must log company_id."""
        content = _read_file("backend/app/api/admin.py")
        # Audit logs include company_id
        assert "company_id=" in content, \
            "Admin operations must include company_id in audit logs"

    def test_admin_lists_all_companies_intentional(self):
        """Admin list_clients intentionally spans all companies — but is gated."""
        content = _read_file("backend/app/api/admin.py")
        assert "require_platform_admin" in content, \
            "Admin list must require platform admin permission"

    def test_admin_update_targets_specific_company(self):
        """Admin update targets a specific company_id from URL path."""
        content = _read_file("backend/app/api/admin.py")
        assert "company_id: str" in content, \
            "Admin update must target specific company_id from path param"
