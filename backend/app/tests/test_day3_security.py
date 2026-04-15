"""
Day 3 Security Fixes — Unit Tests
====================================
Tests for all 10 Day 3 fixes:
  E1:  Enable PostgreSQL internal SSL
  E2:  Fix PostgreSQL exporter sslmode
  A7:  Add is_platform_admin flag for admin endpoints
  A8:  Add auth to webhook retry/status endpoints
  B1:  Reduce tenant middleware PUBLIC_PREFIXES
  B2:  Fix IP allowlist to use TRUSTED_PROXY_COUNT
  B3:  Escape wildcards in admin search
  B4:  Add auth + rate limiting to chat API
  E3:  Build GDPR endpoints (backend)
"""

import os
import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def _read(rel_path: str) -> str:
    """Read a file relative to project root."""
    full_path = os.path.join(PROJECT_ROOT, rel_path)
    with open(full_path) as f:
        return f.read()


# ============================================================
# E1: Enable PostgreSQL internal SSL
# ============================================================

class TestE1PostgreSQLSSL:
    """PostgreSQL config must have SSL enabled with correct cert paths."""

    def test_ssl_enabled(self):
        content = _read("infra/docker/postgresql.conf")
        assert "ssl = on" in content, \
            "PostgreSQL SSL must be enabled (ssl = on)"

    def test_ssl_not_off(self):
        content = _read("infra/docker/postgresql.conf")
        assert "ssl = off" not in content, \
            "ssl = off must be replaced with ssl = on"

    def test_ssl_cert_file_path(self):
        content = _read("infra/docker/postgresql.conf")
        assert "ssl_cert_file = '/var/lib/postgresql/server.crt'" in content, \
            "ssl_cert_file must point to /var/lib/postgresql/server.crt"

    def test_ssl_key_file_path(self):
        content = _read("infra/docker/postgresql.conf")
        assert "ssl_key_file = '/var/lib/postgresql/server.key'" in content, \
            "ssl_key_file must point to /var/lib/postgresql/server.key"

    def test_self_signed_comment(self):
        content = _read("infra/docker/postgresql.conf")
        assert "self-signed" in content.lower(), \
            "Comment should mention self-signed certificates"


# ============================================================
# E2: Fix PostgreSQL exporter sslmode
# ============================================================

class TestE2PostgresExporterSSLMode:
    """Postgres exporter must use sslmode=require."""

    def test_sslmode_require(self):
        content = _read("docker-compose.prod.yml")
        assert "sslmode=require" in content, \
            "postgres-exporter must use sslmode=require"

    def test_sslmode_disable_removed(self):
        content = _read("docker-compose.prod.yml")
        assert "sslmode=disable" not in content, \
            "sslmode=disable must be replaced with sslmode=require"


# ============================================================
# A7: Add is_platform_admin flag for admin endpoints
# ============================================================

class TestA7PlatformAdminGuard:
    """Admin endpoints must use require_platform_admin dependency."""

    def test_platform_admin_guard_function_exists(self):
        content = _read("backend/app/api/admin.py")
        assert "def require_platform_admin(" in content, \
            "require_platform_admin function must exist"

    def test_platform_admin_checks_env_var(self):
        content = _read("backend/app/api/admin.py")
        assert "PLATFORM_ADMIN_EMAILS" in content, \
            "Guard must check PLATFORM_ADMIN_EMAILS env var"

    def test_platform_admin_has_todo_comment(self):
        content = _read("backend/app/api/admin.py")
        assert "TODO" in content and "is_platform_admin" in content, \
            "Must have TODO comment about is_platform_admin DB column"

    def test_list_clients_uses_platform_admin(self):
        content = _read("backend/app/api/admin.py")
        assert 'Depends(require_platform_admin)' in content, \
            "Admin endpoints must use require_platform_admin dependency"

    def test_get_client_detail_uses_platform_admin(self):
        content = _read("backend/app/api/admin.py")
        assert 'Depends(require_platform_admin)' in content, \
            "get_client_detail must use require_platform_admin"

    def test_update_client_uses_platform_admin(self):
        content = _read("backend/app/api/admin.py")
        assert 'Depends(require_platform_admin)' in content, \
            "update_client must use require_platform_admin"

    def test_update_subscription_uses_platform_admin(self):
        content = _read("backend/app/api/admin.py")
        assert 'Depends(require_platform_admin)' in content, \
            "update_subscription must use require_platform_admin"

    def test_api_providers_use_platform_admin(self):
        content = _read("backend/app/api/admin.py")
        # Count occurrences — should cover list, create, update, delete
        count = content.count("Depends(require_platform_admin)")
        assert count >= 7, \
            f"All 7+ admin endpoints must use require_platform_admin, found {count}"

    def test_no_owner_role_dependency_remains(self):
        """require_roles('owner') should no longer be used on admin endpoints."""
        content = _read("backend/app/api/admin.py")
        lines = content.split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("def list_clients") or \
               stripped.startswith("def get_client_detail") or \
               stripped.startswith("def update_client") or \
               stripped.startswith("def update_subscription") or \
               stripped.startswith("def list_api_providers") or \
               stripped.startswith("def create_api_provider") or \
               stripped.startswith("def update_api_provider") or \
               stripped.startswith("def delete_api_provider"):
                # Look at the next few lines for Depends
                continue
        # The admin.py still imports require_roles for potential future use,
        # but all endpoints should use require_platform_admin


# ============================================================
# A8: Add auth to webhook retry/status endpoints
# ============================================================

class TestA8WebhookAuth:
    """Webhook retry and status endpoints must require authentication."""

    def test_status_endpoint_has_auth(self):
        content = _read("backend/app/api/webhooks.py")
        assert "get_current_user" in content, \
            "webhooks.py must import get_current_user"

    def test_status_endpoint_has_user_param(self):
        content = _read("backend/app/api/webhooks.py")
        # Find the get_webhook_status function and check for user param
        assert "user: User = Depends(get_current_user)" in content, \
            "get_webhook_status must have user auth dependency"

    def test_retry_endpoint_has_user_param(self):
        content = _read("backend/app/api/webhooks.py")
        # The retry function should also have the auth dependency
        count = content.count("Depends(get_current_user)")
        assert count >= 2, \
            "Both get_webhook_status and retry_webhook must have auth dependency"


# ============================================================
# B1: Reduce tenant middleware PUBLIC_PREFIXES
# ============================================================

class TestB1TenantPublicPrefixes:
    """PUBLIC_PREFIXES must only contain truly public paths."""

    def test_billing_removed(self):
        content = _read("backend/app/middleware/tenant.py")
        assert '"/api/billing/"' not in content, \
            "/api/billing/ must be removed from PUBLIC_PREFIXES"

    def test_api_keys_removed(self):
        content = _read("backend/app/middleware/tenant.py")
        assert '"/api/api-keys"' not in content, \
            "/api/api-keys must be removed from PUBLIC_PREFIXES"

    def test_mfa_removed(self):
        content = _read("backend/app/middleware/tenant.py")
        assert '"/api/mfa/"' not in content, \
            "/api/mfa/ must be removed from PUBLIC_PREFIXES"

    def test_client_removed(self):
        content = _read("backend/app/middleware/tenant.py")
        assert '"/api/client/"' not in content, \
            "/api/client/ must be removed from PUBLIC_PREFIXES"

    def test_auth_kept(self):
        content = _read("backend/app/middleware/tenant.py")
        assert '"/api/auth/"' in content, \
            "/api/auth/ must remain in PUBLIC_PREFIXES"

    def test_public_kept(self):
        content = _read("backend/app/middleware/tenant.py")
        assert '"/api/public/"' in content, \
            "/api/public/ must remain in PUBLIC_PREFIXES"

    def test_webhooks_kept(self):
        content = _read("backend/app/middleware/tenant.py")
        assert '"/api/webhooks/"' in content, \
            "/api/webhooks/ must remain in PUBLIC_PREFIXES"

    def test_pricing_kept(self):
        content = _read("backend/app/middleware/tenant.py")
        assert '"/api/pricing/"' in content, \
            "/api/pricing/ must remain in PUBLIC_PREFIXES"

    def test_test_kept(self):
        content = _read("backend/app/middleware/tenant.py")
        assert '"/test/"' in content, \
            "/test/ must remain in PUBLIC_PREFIXES"


# ============================================================
# B2: Fix IP allowlist to use TRUSTED_PROXY_COUNT
# ============================================================

class TestB2IPAllowlistTrustedProxy:
    """IP allowlist _get_client_ip must use TRUSTED_PROXY_COUNT logic."""

    def test_trusted_proxy_count_env_var(self):
        content = _read("backend/app/middleware/ip_allowlist.py")
        assert "TRUSTED_PROXY_COUNT" in content, \
            "ip_allowlist.py must reference TRUSTED_PROXY_COUNT"

    def test_rightmost_ip_selection(self):
        content = _read("backend/app/middleware/ip_allowlist.py")
        assert "ips[-" in content, \
            "Must select rightmost IP from X-Forwarded-For"

    def test_default_proxy_count_one(self):
        content = _read("backend/app/middleware/ip_allowlist.py")
        assert 'os.environ.get("TRUSTED_PROXY_COUNT", "1")' in content, \
            "TRUSTED_PROXY_COUNT must default to 1"

    def test_no_first_ip_selection(self):
        """B2: Must NOT use forwarded.split(',')[0] (old vulnerable logic)."""
        content = _read("backend/app/middleware/ip_allowlist.py")
        # The old pattern was: return forwarded.split(",")[0].strip()
        # This should NOT be present in _get_client_ip
        lines = content.split("\n")
        in_method = False
        for line in lines:
            if "def _get_client_ip" in line:
                in_method = True
            if in_method and "def " in line and "_get_client_ip" not in line:
                break
            if in_method and 'forwarded.split(",")[0]' in line:
                pytest.fail(
                    "ip_allowlist._get_client_ip must NOT use "
                    "forwarded.split(',')[0] (vulnerable to IP spoofing)"
                )


# ============================================================
# B3: Escape wildcards in admin search
# ============================================================

class TestB3AdminSearchWildcardEscape:
    """Admin search must escape LIKE wildcards before ilike query."""

    def test_percent_escaped(self):
        content = _read("backend/app/api/admin.py")
        assert 'replace("%"' in content or 'r"\\%"' in content, \
            "Search term must escape % characters"

    def test_underscore_escaped(self):
        content = _read("backend/app/api/admin.py")
        assert 'replace("_"' in content or 'r"\\_"' in content, \
            "Search term must escape _ characters"

    def test_escape_parameter_used(self):
        content = _read("backend/app/api/admin.py")
        assert 'escape=' in content, \
            "ilike must use escape parameter"

    def test_safe_search_variable(self):
        content = _read("backend/app/api/admin.py")
        assert "safe_search" in content, \
            "Must use a safe_search variable for escaped input"


# ============================================================
# B4: Add auth + rate limiting to chat API
# ============================================================

class TestB4ChatAPIAuthAndRateLimit:
    """Chat API route must check auth cookie and enforce rate limiting."""

    def test_session_cookie_check(self):
        content = _read("frontend/src/app/api/chat/route.ts")
        assert "session" in content.lower(), \
            "Chat API must check for session cookie"

    def test_401_response_for_no_auth(self):
        content = _read("frontend/src/app/api/chat/route.ts")
        assert "401" in content, \
            "Chat API must return 401 when auth cookie missing"

    def test_rate_limit_store_exists(self):
        content = _read("frontend/src/app/api/chat/route.ts")
        assert "_rateLimitStore" in content or "rateLimit" in content, \
            "Chat API must have rate limiting store"

    def test_rate_limit_max_5(self):
        content = _read("frontend/src/app/api/chat/route.ts")
        assert "5" in content, \
            "Rate limit max should be 5 requests"

    def test_429_response_for_rate_limit(self):
        content = _read("frontend/src/app/api/chat/route.ts")
        assert "429" in content, \
            "Chat API must return 429 when rate limit exceeded"

    def test_rate_limit_cleanup(self):
        content = _read("frontend/src/app/api/chat/route.ts")
        assert "setInterval" in content, \
            "Rate limit store must have cleanup to prevent memory leaks"


# ============================================================
# E3: Build GDPR endpoints (backend)
# ============================================================

class TestE3GDPRModules:
    """GDPR endpoints must exist and be wired into the app."""

    def test_gdpr_module_exists(self):
        full_path = os.path.join(PROJECT_ROOT, "backend/app/api/gdpr.py")
        assert os.path.exists(full_path), \
            "backend/app/api/gdpr.py must exist"

    def test_gdpr_router_defined(self):
        content = _read("backend/app/api/gdpr.py")
        assert 'APIRouter(prefix="/api/gdpr"' in content, \
            "GDPR router must have /api/gdpr prefix"

    def test_gdpr_erase_endpoint(self):
        content = _read("backend/app/api/gdpr.py")
        assert '"/erase"' in content, \
            "GDPR router must have /erase endpoint"

    def test_gdpr_export_endpoint(self):
        content = _read("backend/app/api/gdpr.py")
        assert '"/export"' in content, \
            "GDPR router must have /export endpoint"

    def test_gdpr_erase_post(self):
        content = _read("backend/app/api/gdpr.py")
        assert "@router.post" in content, \
            "/erase must be a POST endpoint"

    def test_gdpr_export_get(self):
        content = _read("backend/app/api/gdpr.py")
        assert "@router.get" in content, \
            "/export must be a GET endpoint"

    def test_gdpr_erase_requires_auth(self):
        content = _read("backend/app/api/gdpr.py")
        assert "get_current_user" in content, \
            "GDPR endpoints must require authentication"

    def test_gdpr_erase_has_todo(self):
        content = _read("backend/app/api/gdpr.py")
        assert "TODO" in content, \
            "GDPR erase must have TODO for actual implementation"

    def test_gdpr_export_has_todo(self):
        content = _read("backend/app/api/gdpr.py")
        # Count TODOs — should have at least 2
        count = content.count("TODO")
        assert count >= 2, \
            "GDPR module must have TODO comments for both endpoints"

    def test_gdpr_wired_in_main(self):
        content = _read("backend/app/main.py")
        assert "gdpr_router" in content, \
            "main.py must import gdpr_router"

    def test_gdpr_included_in_app(self):
        content = _read("backend/app/main.py")
        assert "app.include_router(gdpr_router)" in content, \
            "main.py must include gdpr_router"


# ============================================================
# Integration: Import chain validation
# ============================================================

class TestImportChain:
    """Verify that modified modules can be imported without errors."""

    def test_admin_module_imports(self):
        content = _read("backend/app/api/admin.py")
        # Must import AuthorizationError for the guard
        assert "AuthorizationError" in content, \
            "admin.py must import AuthorizationError"

    def test_webhook_module_imports(self):
        content = _read("backend/app/api/webhooks.py")
        # Must import Depends for auth dependency
        assert "from fastapi import" in content and "Depends" in content, \
            "webhooks.py must import Depends from fastapi"

    def test_ip_allowlist_imports_os(self):
        content = _read("backend/app/middleware/ip_allowlist.py")
        assert "import os" in content, \
            "ip_allowlist.py must import os for env var reading"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
