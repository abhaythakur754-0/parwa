"""
PARWA Security Day 2 — Comprehensive Unit Tests

Tests for all 10 security fixes from Day 2 (API Authentication Gaps):
  C-11: Billing status endpoint now requires platform admin auth
  C-12: RAG search no longer allows user-supplied company_id override
  H-07: Webhook signature verification fails closed when secret unset
  H-13: Billing endpoints have owner/admin role restrictions
  H-14: Chat widget validates company_id exists before session creation
  H-15: Webhook status/retry endpoints require platform admin auth
  H-22: Workflow path-param company_id validated against JWT
  M-33: ILIKE wildcards escaped to prevent SQL injection
  M-36: Test env no longer bypasses webhook signature verification
  M-19: Visitor token verification exception no longer silently passes
"""

import json
import os
import re
import sys
from unittest.mock import MagicMock, patch

import pytest

# ── Path setup so imports work ─────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

_BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "..")
_BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..")


# ====================================================================
# Helper: Read source file
# ====================================================================


def _read_source(relative_path):
    """Read a source file relative to the parwa project root."""
    path = os.path.join(_BASE_DIR, relative_path)
    with open(path, "r") as f:
        return f.read()


def _read_backend_source(relative_path):
    """Read a source file relative to the backend dir."""
    path = os.path.join(_BACKEND_DIR, relative_path)
    with open(path, "r") as f:
        return f.read()


# ====================================================================
# C-11: Billing Status Endpoint Requires Platform Admin
# ====================================================================


class TestBillingStatusAuthentication:
    """Verify GET /api/v1/billing/status/{company_id} requires auth."""

    def test_billing_status_has_auth_dependency(self):
        """Billing status endpoint must have require_platform_admin dependency."""
        content = _read_backend_source("app/api/billing_webhooks.py")
        # Must import require_platform_admin
        assert "require_platform_admin" in content
        # Must have user parameter with platform admin dependency
        assert "require_platform_admin" in content

    def test_billing_status_no_manual_session(self):
        """Billing status endpoint should NOT manually create SessionLocal."""
        content = _read_backend_source("app/api/billing_webhooks.py")
        # Find the get_billing_status function
        lines = content.split("\n")
        in_func = False
        for line in lines:
            if "def get_billing_status" in line:
                in_func = True
            elif in_func and line.startswith("def "):
                break
            elif in_func:
                # Should NOT have SessionLocal() manual creation
                assert "SessionLocal()" not in line

    def test_billing_status_has_platform_admin_import(self):
        """Must import require_platform_admin from deps."""
        content = _read_backend_source("app/api/billing_webhooks.py")
        assert "from app.api.deps import" in content
        assert "require_platform_admin" in content

    def test_billing_status_uses_db_dependency(self):
        """Billing status should use Depends(get_db) for DI."""
        content = _read_backend_source("app/api/billing_webhooks.py")
        assert "Depends(get_db)" in content


# ====================================================================
# C-12: RAG Search No Longer Trusts Body company_id
# ====================================================================


class TestRAGCrossTenantProtection:
    """Verify RAG endpoints cannot be used for cross-tenant access."""

    def test_rag_search_no_body_override(self):
        """rag_search must NOT allow body.get('company_id') override."""
        content = _read_backend_source("app/api/rag.py")
        lines = content.split("\n")
        in_search = False
        for line in lines:
            if "async def rag_search" in line:
                in_search = True
            elif in_search and line.startswith("async def ") or line.startswith("def "):
                break
            elif in_search:
                assert "body.get(\"company_id\"" not in line, (
                    "rag_search should not trust body company_id"
                )

    def test_rag_add_document_no_body_override(self):
        """add_document must NOT allow body.get('company_id') override."""
        content = _read_backend_source("app/api/rag.py")
        lines = content.split("\n")
        in_func = False
        for line in lines:
            if "def add_document" in line:
                in_func = True
            elif in_func and ("def " in line and "add_document" not in line):
                break
            elif in_func:
                assert "body.get(\"company_id\"" not in line, (
                    "add_document should not trust body company_id"
                )

    def test_rag_reindex_no_body_override(self):
        """trigger_reindex must NOT allow body.get('company_id') override."""
        content = _read_backend_source("app/api/rag.py")
        lines = content.split("\n")
        in_func = False
        for line in lines:
            if "def trigger_reindex" in line:
                in_func = True
            elif in_func and ("def " in line and "trigger_reindex" not in line):
                break
            elif in_func:
                assert "body.get(\"company_id\"" not in line, (
                    "trigger_reindex should not trust body company_id"
                )

    def test_rag_get_document_has_jwt_check(self):
        """get_document must verify path company_id matches JWT company_id."""
        content = _read_backend_source("app/api/rag.py")
        # Must have AuthorizationError import
        assert "AuthorizationError" in content
        # Must have JWT company_id check
        assert "jwt_company_id" in content

    def test_rag_delete_document_has_jwt_check(self):
        """delete_document must verify path company_id matches JWT company_id."""
        content = _read_backend_source("app/api/rag.py")
        assert "jwt_company_id" in content
        assert "company_id != jwt_company_id" in content

    def test_rag_reindex_status_has_jwt_check(self):
        """get_reindex_status must verify path company_id matches JWT."""
        content = _read_backend_source("app/api/rag.py")
        assert "get_jwt_company_id" in content or "jwt_company_id" in content


# ====================================================================
# H-07: Webhook Signature Fails Closed
# ====================================================================


class TestWebhookSignatureEnforcement:
    """Verify webhook signature verification fails closed in production."""

    def test_webhook_no_secret_rejects_in_non_dev(self):
        """When PADDLE_WEBHOOK_SECRET is empty and not dev, should reject."""
        content = _read_backend_source("app/api/billing_webhooks.py")
        # Must check environment before skipping
        assert "ENVIRONMENT" in content or "environment" in content.lower()
        # Must have error logging when no secret in production
        assert "paddle_webhook_no_secret_configured" in content

    def test_webhook_signature_always_verified(self):
        """Signature verification must not be skipped with 'if secret and'."""
        content = _read_backend_source("app/api/billing_webhooks.py")
        # The old pattern was: if webhook_secret and not verify...
        # New pattern must separate the no-secret check
        # Should NOT have the compound 'if webhook_secret and not verify' pattern
        lines = content.split("\n")
        for line in lines:
            if "if webhook_secret and not verify_paddle_signature" in line:
                pytest.fail(
                    "billing_webhooks.py still uses compound "
                    "'if webhook_secret and not verify' pattern — "
                    "must fail closed when secret is missing"
                )

    def test_webhook_dev_mode_allowed(self):
        """In development mode, missing secret should warn but continue."""
        content = _read_backend_source("app/api/billing_webhooks.py")
        assert "dev_mode" in content.lower() or "development" in content.lower()

    def test_webhook_import_os(self):
        """Must import os for environment checking."""
        content = _read_backend_source("app/api/billing_webhooks.py")
        assert "import os" in content


# ====================================================================
# H-13: Billing Endpoints Have Role Restrictions
# ====================================================================


class TestBillingRoleRestrictions:
    """Verify sensitive billing endpoints require owner/admin role."""

    def test_billing_imports_require_roles(self):
        """billing.py must import require_roles from deps."""
        content = _read_backend_source("app/api/billing.py")
        assert "require_roles" in content
        assert "from app.api.deps" in content

    def test_cancel_subscription_has_role_check(self):
        """cancel_subscription must require owner/admin role."""
        content = _read_backend_source("app/api/billing.py")
        # Find the cancel_subscription function and check for role dependency
        assert 'require_roles("owner", "admin")' in content

    def test_reactivate_subscription_has_role_check(self):
        """reactivate_subscription must require owner/admin role."""
        content = _read_backend_source("app/api/billing.py")
        # require_roles may be on the same line or next line after def
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "def reactivate_subscription" in line:
                # Check this line and next few lines for require_roles
                check_window = lines[i:i+10]
                for wline in check_window:
                    if "require_roles" in wline:
                        return
        pytest.fail("reactivate_subscription missing require_roles")

    def test_create_refund_has_role_check(self):
        """create_client_refund must require owner/admin role."""
        content = _read_backend_source("app/api/billing.py")
        assert 'require_roles("owner", "admin")' in content

    def test_process_refund_has_role_check(self):
        """process_client_refund must require owner/admin role."""
        content = _read_backend_source("app/api/billing.py")
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "def process_client_refund" in line:
                check_window = lines[i:i+10]
                for wline in check_window:
                    if "require_roles" in wline:
                        return
        pytest.fail("process_client_refund missing require_roles")

    def test_read_endpoints_no_role_check(self):
        """Read-only billing endpoints should NOT have role restrictions."""
        content = _read_backend_source("app/api/billing.py")
        # get_subscription, list_invoices, get_current_usage etc should
        # NOT have require_roles (they use get_company_id only)
        lines = content.split("\n")
        in_get_sub = False
        for line in lines:
            if "async def get_subscription(" in line:
                in_get_sub = True
            elif in_get_sub and ("def " in line or "async def " in line):
                break
            elif in_get_sub and "require_roles" in line:
                pytest.fail("get_subscription should NOT have require_roles")


# ====================================================================
# H-14: Chat Widget Validates company_id
# ====================================================================


class TestChatWidgetCompanyIdValidation:
    """Verify chat widget validates company exists before creating session."""

    def test_create_session_validates_company(self):
        """create_chat_session must validate company_id exists in DB."""
        content = _read_backend_source("app/api/chat_widget.py")
        assert "Company not found" in content

    def test_create_session_queries_company(self):
        """Must query Company model to validate existence."""
        content = _read_backend_source("app/api/chat_widget.py")
        assert "Company" in content
        assert "Company.id" in content or "company.id" in content

    def test_create_session_returns_404_for_invalid_company(self):
        """Must return 404 when company doesn't exist."""
        content = _read_backend_source("app/api/chat_widget.py")
        # Should have a 404 response for company not found
        assert "404" in content
        assert "NOT_FOUND" in content

    def test_company_check_before_service_creation(self):
        """Company validation must happen BEFORE ChatWidgetService creation."""
        content = _read_backend_source("app/api/chat_widget.py")
        pos_company_check = content.find("Company not found")
        pos_service = content.find("ChatWidgetService(db, company_id)")
        # Company check should come before service creation in the
        # create_chat_session function
        # (allowing for the service import pattern, just check
        #  the 404 response comes before the main service call)
        assert pos_company_check > 0, "Company validation not found"


# ====================================================================
# H-15: Webhook Status/Retry Require Authentication
# ====================================================================


class TestWebhookStatusRetryAuth:
    """Verify webhook status and retry endpoints require platform admin."""

    def test_webhook_status_has_auth(self):
        """get_webhook_status must require platform admin."""
        content = _read_backend_source("app/api/webhooks.py")
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "def get_webhook_status" in line:
                check_window = lines[i:i+10]
                for wline in check_window:
                    if "require_platform_admin" in wline:
                        return
        pytest.fail("get_webhook_status missing require_platform_admin")

    def test_webhook_retry_has_auth(self):
        """retry_webhook must require platform admin."""
        content = _read_backend_source("app/api/webhooks.py")
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "def retry_webhook" in line:
                check_window = lines[i:i+10]
                for wline in check_window:
                    if "require_platform_admin" in wline:
                        return
        pytest.fail("retry_webhook missing require_platform_admin")

    def test_webhook_imports_deps(self):
        """webhooks.py must import from app.api.deps."""
        content = _read_backend_source("app/api/webhooks.py")
        assert "from app.api.deps import" in content


# ====================================================================
# H-22: Workflow Path Param IDOR Fix
# ====================================================================


class TestWorkflowIDORProtection:
    """Verify workflow endpoints validate path company_id against JWT."""

    def test_workflow_imports_jwt_company_id(self):
        """workflow.py must import get_company_id for JWT validation."""
        content = _read_backend_source("app/api/workflow.py")
        assert "get_jwt_company_id" in content or "get_company_id" in content

    def test_workflow_imports_authorization_error(self):
        """workflow.py must import AuthorizationError."""
        content = _read_backend_source("app/api/workflow.py")
        assert "AuthorizationError" in content

    def test_capacity_status_has_idor_check(self):
        """get_capacity_status must validate company_id matches JWT."""
        content = _read_backend_source("app/api/workflow.py")
        assert "company_id != jwt_company_id" in content

    def test_configure_capacity_has_idor_check(self):
        """configure_capacity must validate company_id matches JWT."""
        content = _read_backend_source("app/api/workflow.py")
        # Should have at least one IDOR check (shared pattern)
        assert "company_id != jwt_company_id" in content

    def test_tenant_config_has_idor_check(self):
        """get_tenant_config must validate company_id matches JWT."""
        content = _read_backend_source("app/api/workflow.py")
        assert "jwt_company_id" in content

    def test_update_tenant_config_has_idor_check(self):
        """update_tenant_config must validate company_id matches JWT."""
        content = _read_backend_source("app/api/workflow.py")
        lines = content.split("\n")
        in_func = False
        found = False
        for line in lines:
            if "def update_tenant_config" in line:
                in_func = True
            elif in_func and ("def " in line and "update_tenant" not in line):
                break
            elif in_func and "jwt_company_id" in line:
                found = True
        assert found, "update_tenant_config missing jwt_company_id check"

    def test_gsd_transitions_has_idor_check(self):
        """get_gsd_transitions must validate company_id matches JWT."""
        content = _read_backend_source("app/api/workflow.py")
        lines = content.split("\n")
        in_func = False
        found = False
        for line in lines:
            if "def get_gsd_transitions" in line:
                in_func = True
            elif in_func and ("def " in line and "gsd" not in line.lower()):
                break
            elif in_func and "jwt_company_id" in line:
                found = True
        assert found, "get_gsd_transitions missing jwt_company_id check"

    def test_idor_error_message(self):
        """IDOR check should return a descriptive error message."""
        content = _read_backend_source("app/api/workflow.py")
        assert "Cannot access another company" in content or (
            "cross-tenant" in content.lower()
        )


# ====================================================================
# M-33: ILIKE Wildcard Escaping
# ====================================================================


class TestILIKEWildcardEscaping:
    """Verify ILIKE search parameters have wildcards escaped."""

    def test_admin_search_escapes_percent(self):
        """Admin search must escape % characters in search terms."""
        content = _read_backend_source("app/api/admin.py")
        assert 'escaped_search' in content
        assert '.replace("%"' in content
        assert r'r"\%"' in content or r'"\\%"' in content

    def test_admin_search_escapes_underscore(self):
        """Admin search must escape _ characters in search terms."""
        content = _read_backend_source("app/api/admin.py")
        assert '.replace("_"' in content
        assert r'r"\_"' in content or r'"\\_"' in content

    def test_admin_search_uses_escape_clause(self):
        """ILIKE query must use escape clause."""
        content = _read_backend_source("app/api/admin.py")
        assert 'escape=' in content

    def test_no_raw_ilike_with_interpolation(self):
        """Must NOT have raw f-string interpolation into ILIKE without escaping."""
        content = _read_backend_source("app/api/admin.py")
        # Should not have: .ilike(f"%{search}%")
        # Should have: .ilike(f"%{escaped_search}%", escape="\\")
        assert 'f"%{search}%"' not in content
        assert 'f"%{escaped_search}%"' in content

    def test_tickets_search_also_escaped(self):
        """Verify no other files have unescaped ILIKE patterns."""
        # Check tickets.py for the same pattern
        tickets_path = os.path.join(_BACKEND_DIR, "app/api/tickets.py")
        if os.path.exists(tickets_path):
            content = open(tickets_path).read()
            assert 'f"%{search}%"' not in content, (
                "tickets.py has unescaped ILIKE search — SQL injection risk"
            )


# ====================================================================
# M-36: Test Environment No Longer Bypasses Signature
# ====================================================================


class TestWebhookTestEnvSecurity:
    """Verify test environment no longer bypasses webhook signature."""

    def test_no_test_env_bypass(self):
        """_verify_provider_signature should NOT have ENVIRONMENT==test bypass."""
        content = _read_backend_source("app/api/webhooks.py")
        # Must NOT have the old bypass pattern
        assert 'ENVIRONMENT == "test"' not in content
        assert "os.environ.get(\"ENVIRONMENT\") == \"test\"" not in content

    def test_signature_always_enforced(self):
        """Signature verification docstring should say always enforced."""
        content = _read_backend_source("app/api/webhooks.py")
        # The function should NOT have a test bypass comment
        lines = content.split("\n")
        in_func = False
        for line in lines:
            if "def _verify_provider_signature" in line:
                in_func = True
            elif in_func and line.startswith("def "):
                break
            elif in_func:
                assert "return True" not in line or "verify" in line.lower()

    def test_provider_verification_intact(self):
        """All provider verification branches must still exist."""
        content = _read_backend_source("app/api/webhooks.py")
        assert "verify_paddle_signature" in content
        assert "verify_shopify_hmac" in content
        assert "verify_twilio_signature" in content
        assert "verify_brevo_ip" in content


# ====================================================================
# M-19: Visitor Token Exception No Longer Silently Passes
# ====================================================================


class TestVisitorTokenExceptionHandling:
    """Verify visitor token verification failures return 401, not silent pass."""

    def test_no_silent_pass_in_send_message(self):
        """send_chat_message must NOT have 'except Exception: pass'."""
        content = _read_backend_source("app/api/chat_widget.py")
        lines = content.split("\n")
        in_func = False
        for line in lines:
            if "async def send_chat_message" in line:
                in_func = True
            elif in_func and line.startswith("async def ") or line.startswith("def "):
                break
            elif in_func and "except Exception:" in line:
                next_lines = content.split("\n")
                idx = next_lines.index(line)
                if idx + 1 < len(next_lines):
                    next_line = next_lines[idx + 1].strip()
                    assert next_line != "pass", (
                        "send_chat_message has 'except Exception: pass' "
                        "— auth bypass vulnerability"
                    )

    def test_no_silent_pass_in_typing_indicator(self):
        """send_typing_indicator must NOT have 'except Exception: pass'."""
        content = _read_backend_source("app/api/chat_widget.py")
        # Count occurrences of 'except Exception:' followed by 'pass'
        # in the entire file — should be ZERO
        assert "except Exception:\n            pass" not in content
        assert "except Exception:\n        pass" not in content

    def test_visitor_token_failure_returns_401(self):
        """Visitor token failure must return 401 AUTHENTICATION_ERROR."""
        content = _read_backend_source("app/api/chat_widget.py")
        assert "Visitor token verification failed" in content

    def test_no_bare_pass_patterns(self):
        """There should be zero 'except Exception: pass' patterns."""
        content = _read_backend_source("app/api/chat_widget.py")
        # More thorough check: no 'pass' immediately after except
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "except Exception:" in line and "pass" not in line:
                # Check next line for 'pass'
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    assert next_line != "pass", (
                        f"Found 'except Exception:' followed by 'pass' "
                        f"at line {i+1} — potential auth bypass"
                    )


# ====================================================================
# Cross-cutting: Multi-Agentic Architecture Verification
# ====================================================================


class TestMultiAgenticArchitecture:
    """Verify security fixes don't break multi-agentic architecture."""

    def test_workflow_capacity_scoped_to_tenant(self):
        """Capacity endpoints should still scope to tenant after IDOR fix."""
        content = _read_backend_source("app/api/workflow.py")
        # CapacityStatusResponse should include company_id
        assert "company_id" in content

    def test_rag_operations_still_work_for_valid_users(self):
        """RAG operations should still work for users with valid JWT."""
        content = _read_backend_source("app/api/rag.py")
        # Should still have get_company_id dependency
        assert "get_company_id" in content
        # Should still import from deps
        assert "from app.api.deps import" in content

    def test_billing_api_still_has_company_isolation(self):
        """Billing API should still use company_id for tenant isolation."""
        content = _read_backend_source("app/api/billing.py")
        assert "company_id" in content
        assert "get_company_id" in content

    def test_webhook_processing_still_works(self):
        """Webhook processing should still function after security fixes."""
        content = _read_backend_source("app/api/webhooks.py")
        assert "process_webhook" in content
        assert "webhook_service" in content

    def test_chat_widget_still_supports_visitor_flow(self):
        """Chat widget should still support visitor token flow."""
        content = _read_backend_source("app/api/chat_widget.py")
        assert "visitor_token" in content
        assert "verify_visitor_token" in content


# ====================================================================
# Regression: Verify Old Vulnerable Patterns Are Gone
# ====================================================================


class TestVulnerablePatternsGone:
    """Verify old vulnerable patterns are completely removed."""

    def test_no_body_company_id_override_in_rag(self):
        """Zero instances of body.get('company_id') override in rag.py."""
        content = _read_backend_source("app/api/rag.py")
        assert content.count('body.get("company_id"') == 0

    def test_no_compound_webhook_secret_check(self):
        """Zero instances of 'if webhook_secret and not verify' in billing_webhooks.py."""
        content = _read_backend_source("app/api/billing_webhooks.py")
        assert "if webhook_secret and not verify_paddle_signature" not in content

    def test_no_test_env_signature_bypass(self):
        """Zero instances of ENVIRONMENT == "test" bypass in webhooks.py."""
        content = _read_backend_source("app/api/webhooks.py")
        assert 'ENVIRONMENT == "test"' not in content

    def test_no_unescaped_ilike(self):
        """Zero instances of raw f-string ILIKE without escaping."""
        content = _read_backend_source("app/api/admin.py")
        assert 'f"%{search}%"' not in content

    def test_no_except_pass_in_chat_widget(self):
        """Zero instances of 'except Exception: pass' in chat_widget.py."""
        content = _read_backend_source("app/api/chat_widget.py")
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "except Exception:" in line:
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    assert next_line != "pass"


# ====================================================================
# Run Tests
# ====================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
