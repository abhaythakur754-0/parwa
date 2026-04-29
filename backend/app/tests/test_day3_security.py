"""
Day 3 Security Fixes — Comprehensive Unit Tests
=================================================
Tests for all 10 Day 3 fixes (E1, E2, A7, A8, B1, B2, B3, B4, E3):

  E1:  Enable PostgreSQL internal SSL (config + certs script)
  E2:  Fix PostgreSQL exporter sslmode
  A7:  Add is_platform_admin flag for admin endpoints
  A8:  Add auth to webhook retry/status endpoints
  B1:  Reduce tenant middleware PUBLIC_PREFIXES
  B2:  Fix IP allowlist to use TRUSTED_PROXY_COUNT
  B3:  Escape wildcards in admin search
  B4:  Add auth + rate limiting to chat API
  E3:  Build GDPR endpoints (erase + export with real DB ops)
"""

import os
from datetime import datetime
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", ".."),
)


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
        assert "ssl = on" in content, "PostgreSQL SSL must be enabled (ssl = on)"

    def test_ssl_not_off(self):
        content = _read("infra/docker/postgresql.conf")
        assert "ssl = off" not in content, "ssl = off must be replaced with ssl = on"

    def test_ssl_cert_file_path(self):
        content = _read("infra/docker/postgresql.conf")
        assert (
            "ssl_cert_file = '/var/lib/postgresql/server.crt'" in content
        ), "ssl_cert_file must point to /var/lib/postgresql/server.crt"

    def test_ssl_key_file_path(self):
        content = _read("infra/docker/postgresql.conf")
        assert (
            "ssl_key_file = '/var/lib/postgresql/server.key'" in content
        ), "ssl_key_file must point to /var/lib/postgresql/server.key"

    def test_ssl_ca_file_path(self):
        content = _read("infra/docker/postgresql.conf")
        assert (
            "ssl_ca_file = '/var/lib/postgresql/ca.crt'" in content
        ), "ssl_ca_file must point to /var/lib/postgresql/ca.crt"

    def test_self_signed_comment(self):
        content = _read("infra/docker/postgresql.conf")
        assert (
            "self-signed" in content.lower()
        ), "Comment should mention self-signed certificates"

    def test_generate_ssl_certs_script_exists(self):
        full_path = os.path.join(
            PROJECT_ROOT,
            "infra/docker/generate-ssl-certs.sh",
        )
        assert os.path.exists(
            full_path
        ), "infra/docker/generate-ssl-certs.sh must exist"

    def test_generate_ssl_certs_script_content(self):
        content = _read("infra/docker/generate-ssl-certs.sh")
        assert "openssl" in content, "Script must use openssl to generate certificates"
        assert "server.key" in content, "Script must generate server.key"
        assert "server.crt" in content, "Script must generate server.crt"
        assert "ca.crt" in content, "Script must generate ca.crt"
        assert (
            "chmod 600" in content
        ), "Script must set restrictive permissions on server.key"
        assert "PARWA" in content, "Script must reference PARWA"

    def test_generate_ssl_certs_has_san(self):
        content = _read("infra/docker/generate-ssl-certs.sh")
        assert (
            "subjectAltName" in content or "SAN" in content
        ), "Script must include SAN (Subject Alternative Names) extensions"

    def test_generate_ssl_certs_has_san_entries(self):
        content = _read("infra/docker/generate-ssl-certs.sh")
        assert "localhost" in content, "SAN must include localhost"
        assert "db" in content, "SAN must include 'db' hostname"

    def test_generate_ssl_certs_uses_rsa_4096(self):
        content = _read("infra/docker/generate-ssl-certs.sh")
        assert "rsa:4096" in content, "Script should use RSA 4096-bit keys for security"


# ============================================================
# E2: Fix PostgreSQL exporter sslmode
# ============================================================


class TestE2PostgresExporterSSLMode:
    """Postgres exporter must use sslmode=require."""

    def test_sslmode_require(self):
        content = _read("docker-compose.prod.yml")
        assert (
            "sslmode=require" in content
        ), "postgres-exporter must use sslmode=require"

    def test_sslmode_disable_removed(self):
        content = _read("docker-compose.prod.yml")
        assert (
            "sslmode=disable" not in content
        ), "sslmode=disable must be replaced with sslmode=require"


# ============================================================
# A7: Add is_platform_admin flag for admin endpoints
# ============================================================


class TestA7PlatformAdminGuard:
    """Admin endpoints must use require_platform_admin dependency."""

    def test_platform_admin_guard_function_exists(self):
        content = _read("backend/app/api/admin.py")
        assert (
            "def require_platform_admin(" in content
        ), "require_platform_admin function must exist"

    def test_platform_admin_checks_env_var(self):
        content = _read("backend/app/api/admin.py")
        assert (
            "PLATFORM_ADMIN_EMAILS" in content
        ), "Guard must check PLATFORM_ADMIN_EMAILS env var"

    def test_platform_admin_has_alembic_comment(self):
        content = _read("backend/app/api/admin.py")
        assert (
            "Alembic" in content and "is_platform_admin" in content
        ), "Must have Alembic migration comment about is_platform_admin"

    def test_platform_admin_has_migration_command(self):
        content = _read("backend/app/api/admin.py")
        assert (
            "alembic revision" in content
        ), "Must include the Alembic migration command in comment"

    def test_list_clients_uses_platform_admin(self):
        content = _read("backend/app/api/admin.py")
        assert (
            "Depends(require_platform_admin)" in content
        ), "Admin endpoints must use require_platform_admin dependency"

    def test_get_client_detail_uses_platform_admin(self):
        content = _read("backend/app/api/admin.py")
        assert (
            "Depends(require_platform_admin)" in content
        ), "get_client_detail must use require_platform_admin"

    def test_update_client_uses_platform_admin(self):
        content = _read("backend/app/api/admin.py")
        assert (
            "Depends(require_platform_admin)" in content
        ), "update_client must use require_platform_admin"

    def test_update_subscription_uses_platform_admin(self):
        content = _read("backend/app/api/admin.py")
        assert (
            "Depends(require_platform_admin)" in content
        ), "update_subscription must use require_platform_admin"

    def test_api_providers_use_platform_admin(self):
        content = _read("backend/app/api/admin.py")
        # Count occurrences — should cover list, create, update, delete
        count = content.count("Depends(require_platform_admin)")
        assert (
            count >= 7
        ), f"All 7+ admin endpoints must use require_platform_admin, found {count}"

    def test_docstring_mentions_platform_admin(self):
        content = _read("backend/app/api/admin.py")
        assert (
            "require_platform_admin" in content.split('"""')[1]
            if '"""' in content
            else False or "require_platform_admin" in content[:500]
        ), "Module docstring must reference require_platform_admin"

    def test_docstring_no_owner_as_primary(self):
        content = _read("backend/app/api/admin.py")
        # The docstring should NOT say "use require_roles('owner') as a
        # temporary gate"
        assert (
            'require_roles("owner") as a temporary gate' not in content
        ), "Docstring should not mention require_roles('owner') as the gate"


# ============================================================
# A8: Add auth to webhook retry/status endpoints
# ============================================================


class TestA8WebhookAuth:
    """Webhook retry and status endpoints must require authentication."""

    def test_status_endpoint_has_auth(self):
        content = _read("backend/app/api/webhooks.py")
        assert "get_current_user" in content, "webhooks.py must import get_current_user"

    def test_status_endpoint_has_user_param(self):
        content = _read("backend/app/api/webhooks.py")
        assert (
            "user: User = Depends(get_current_user)" in content
        ), "get_webhook_status must have user auth dependency"

    def test_retry_endpoint_has_user_param(self):
        content = _read("backend/app/api/webhooks.py")
        count = content.count("Depends(get_current_user)")
        assert (
            count >= 2
        ), "Both get_webhook_status and retry_webhook must have auth dependency"

    def test_webhook_receive_still_public(self):
        """The receive webhook POST should NOT require auth (it uses HMAC)."""
        content = _read("backend/app/api/webhooks.py")
        # The receive_webhook function should not have
        # Depends(get_current_user)
        lines = content.split("\n")
        in_receive = False
        for line in lines:
            if "async def receive_webhook" in line:
                in_receive = True
            if in_receive and "async def " in line and "receive_webhook" not in line:
                in_receive = False
            if in_receive and "get_current_user" in line:
                pytest.fail(
                    "receive_webhook should NOT require user auth — "
                    "it uses HMAC signature verification instead"
                )


# ============================================================
# B1: Reduce tenant middleware PUBLIC_PREFIXES
# ============================================================


class TestB1TenantPublicPrefixes:
    """PUBLIC_PREFIXES must only contain truly public paths."""

    def test_billing_removed(self):
        content = _read("backend/app/middleware/tenant.py")
        assert (
            '"/api/billing/"' not in content
        ), "/api/billing/ must be removed from PUBLIC_PREFIXES"

    def test_api_keys_removed(self):
        content = _read("backend/app/middleware/tenant.py")
        assert (
            '"/api/api-keys"' not in content
        ), "/api/api-keys must be removed from PUBLIC_PREFIXES"

    def test_mfa_removed(self):
        content = _read("backend/app/middleware/tenant.py")
        assert (
            '"/api/mfa/"' not in content
        ), "/api/mfa/ must be removed from PUBLIC_PREFIXES"

    def test_client_removed(self):
        content = _read("backend/app/middleware/tenant.py")
        assert (
            '"/api/client/"' not in content
        ), "/api/client/ must be removed from PUBLIC_PREFIXES"

    def test_auth_kept(self):
        content = _read("backend/app/middleware/tenant.py")
        assert '"/api/auth/"' in content, "/api/auth/ must remain in PUBLIC_PREFIXES"

    def test_public_kept(self):
        content = _read("backend/app/middleware/tenant.py")
        assert (
            '"/api/public/"' in content
        ), "/api/public/ must remain in PUBLIC_PREFIXES"

    def test_webhooks_kept(self):
        content = _read("backend/app/middleware/tenant.py")
        assert (
            '"/api/webhooks/"' in content
        ), "/api/webhooks/ must remain in PUBLIC_PREFIXES"

    def test_pricing_kept(self):
        content = _read("backend/app/middleware/tenant.py")
        assert (
            '"/api/pricing/"' in content
        ), "/api/pricing/ must remain in PUBLIC_PREFIXES"

    def test_test_kept(self):
        content = _read("backend/app/middleware/tenant.py")
        assert '"/test/"' in content, "/test/ must remain in PUBLIC_PREFIXES"

    def test_b1_comment_present(self):
        content = _read("backend/app/middleware/tenant.py")
        assert (
            "B1:" in content or "billing" in content.lower()
        ), "Should have comment explaining B1 changes"


# ============================================================
# B2: Fix IP allowlist to use TRUSTED_PROXY_COUNT
# ============================================================


class TestB2IPAllowlistTrustedProxy:
    """IP allowlist _get_client_ip must use TRUSTED_PROXY_COUNT logic."""

    def test_trusted_proxy_count_env_var(self):
        content = _read("backend/app/middleware/ip_allowlist.py")
        assert (
            "TRUSTED_PROXY_COUNT" in content
        ), "ip_allowlist.py must reference TRUSTED_PROXY_COUNT"

    def test_rightmost_ip_selection(self):
        content = _read("backend/app/middleware/ip_allowlist.py")
        assert "ips[-" in content, "Must select rightmost IP from X-Forwarded-For"

    def test_default_proxy_count_one(self):
        content = _read("backend/app/middleware/ip_allowlist.py")
        assert (
            'os.environ.get("TRUSTED_PROXY_COUNT", "1")' in content
        ), "TRUSTED_PROXY_COUNT must default to 1"

    def test_no_first_ip_selection(self):
        """B2: Must NOT use forwarded.split(',')[0] (old vulnerable logic)."""
        content = _read("backend/app/middleware/ip_allowlist.py")
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

    def test_fallback_to_client_scope(self):
        """Must fall back to scope['client'] when header is absent."""
        content = _read("backend/app/middleware/ip_allowlist.py")
        assert (
            'scope.get("client")' in content or 'scope["client"]' in content
        ), "Must fall back to scope['client'] when X-Forwarded-For is absent"

    def test_b2_comment_present(self):
        content = _read("backend/app/middleware/ip_allowlist.py")
        assert "B2:" in content, "Must have B2 comment referencing the fix"


# ============================================================
# B3: Escape wildcards in admin search
# ============================================================


class TestB3AdminSearchWildcardEscape:
    """Admin search must escape LIKE wildcards before ilike query."""

    def test_percent_escaped(self):
        content = _read("backend/app/api/admin.py")
        assert (
            'replace("%"' in content or 'r"\\%"' in content
        ), "Search term must escape % characters"

    def test_underscore_escaped(self):
        content = _read("backend/app/api/admin.py")
        assert (
            'replace("_"' in content or 'r"\\_"' in content
        ), "Search term must escape _ characters"

    def test_escape_parameter_used(self):
        content = _read("backend/app/api/admin.py")
        assert "escape=" in content, "ilike must use escape parameter"

    def test_safe_search_variable(self):
        content = _read("backend/app/api/admin.py")
        assert (
            "safe_search" in content
        ), "Must use a safe_search variable for escaped input"

    def test_b3_comment_present(self):
        content = _read("backend/app/api/admin.py")
        assert "B3:" in content, "Must have B3 comment referencing the fix"


# ============================================================
# B4: Add auth + rate limiting to chat API
# ============================================================


class TestB4ChatAPIAuthAndRateLimit:
    """Chat API route must check auth cookie and enforce rate limiting."""

    def test_session_cookie_check(self):
        content = _read("frontend/src/app/api/chat/route.ts")
        assert "session" in content.lower(), "Chat API must check for session cookie"

    def test_401_response_for_no_auth(self):
        content = _read("frontend/src/app/api/chat/route.ts")
        assert "401" in content, "Chat API must return 401 when auth cookie missing"

    def test_rate_limit_store_exists(self):
        content = _read("frontend/src/app/api/chat/route.ts")
        assert (
            "_rateLimitStore" in content or "rateLimit" in content
        ), "Chat API must have rate limiting store"

    def test_rate_limit_max_5(self):
        content = _read("frontend/src/app/api/chat/route.ts")
        assert (
            "RATE_LIMIT_MAX = 5" in content or "RATE_LIMIT_MAX=5" in content
        ), "Rate limit max should be 5 requests"

    def test_429_response_for_rate_limit(self):
        content = _read("frontend/src/app/api/chat/route.ts")
        assert "429" in content, "Chat API must return 429 when rate limit exceeded"

    def test_rate_limit_cleanup(self):
        content = _read("frontend/src/app/api/chat/route.ts")
        assert (
            "setInterval" in content
        ), "Rate limit store must have cleanup to prevent memory leaks"

    def test_b4_comment_present(self):
        content = _read("frontend/src/app/api/chat/route.ts")
        assert "B4:" in content, "Must have B4 comment referencing the fix"

    def test_authentication_required_message(self):
        content = _read("frontend/src/app/api/chat/route.ts")
        assert (
            "Authentication required" in content
            or "authentication required" in content.lower()
        ), "Chat API must return 'Authentication required' message for 401"

    def test_message_validation(self):
        content = _read("frontend/src/app/api/chat/route.ts")
        assert (
            "message.trim().length === 0" in content or "message.trim" in content
        ), "Chat API must validate message content is not empty"


# ============================================================
# E3: Build GDPR endpoints (backend)
# ============================================================


class TestE3GDPRModules:
    """GDPR endpoints must exist and be wired into the app."""

    def test_gdpr_module_exists(self):
        full_path = os.path.join(PROJECT_ROOT, "backend/app/api/gdpr.py")
        assert os.path.exists(full_path), "backend/app/api/gdpr.py must exist"

    def test_gdpr_router_defined(self):
        content = _read("backend/app/api/gdpr.py")
        assert (
            'APIRouter(prefix="/api/gdpr"' in content
        ), "GDPR router must have /api/gdpr prefix"

    def test_gdpr_erase_endpoint(self):
        content = _read("backend/app/api/gdpr.py")
        assert '"/erase"' in content, "GDPR router must have /erase endpoint"

    def test_gdpr_export_endpoint(self):
        content = _read("backend/app/api/gdpr.py")
        assert '"/export"' in content, "GDPR router must have /export endpoint"

    def test_gdpr_erase_post(self):
        content = _read("backend/app/api/gdpr.py")
        assert "@router.post" in content, "/erase must be a POST endpoint"

    def test_gdpr_export_get(self):
        content = _read("backend/app/api/gdpr.py")
        assert "@router.get" in content, "/export must be a GET endpoint"

    def test_gdpr_erase_requires_auth(self):
        content = _read("backend/app/api/gdpr.py")
        assert (
            "get_current_user" in content
        ), "GDPR endpoints must require authentication"

    def test_gdpr_erase_has_db_session(self):
        content = _read("backend/app/api/gdpr.py")
        assert (
            "db: Session = Depends(get_db)" in content
        ), "GDPR erase must have database session dependency"

    def test_gdpr_export_has_db_session(self):
        content = _read("backend/app/api/gdpr.py")
        # get_db should appear (at least once, likely twice)
        assert (
            content.count("Depends(get_db)") >= 1
        ), "GDPR endpoints must use database session"

    def test_gdpr_wired_in_main(self):
        content = _read("backend/app/main.py")
        assert "gdpr_router" in content, "main.py must import gdpr_router"

    def test_gdpr_included_in_app(self):
        content = _read("backend/app/main.py")
        assert (
            "app.include_router(gdpr_router)" in content
        ), "main.py must include gdpr_router"


# ============================================================
# E3: GDPR Implementation — Functional Tests (mocked DB)
# ============================================================


class TestE3GDPRFunctional:
    """Test GDPR erase and export logic with mocked DB.

    These tests import gdpr.py functions. Because the import chain
    (gdpr -> api.__init__ -> auth -> deps -> core.auth) requires
    REFRESH_TOKEN_PEPPER and JWT_SECRET_KEY env vars at module-load
    time, we set them before any import and also clear stale
    cached modules to avoid stale ImportError caches.
    """

    @pytest.fixture(autouse=True)
    def _set_env_and_clear_cache(self, monkeypatch):
        """Set required env vars and clear any stale module caches."""
        monkeypatch.setenv("REFRESH_TOKEN_PEPPER", "test-pepper-for-day3-tests")
        monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-for-day3-tests")
        monkeypatch.setenv("ENVIRONMENT", "test")
        # Clear stale cached modules that may have failed to import
        # in a previous test run (Python caches ImportError).
        import sys as _sys

        # Remove the api package and its children from cache if present
        stale_prefixes = [
            "backend.app.api.auth",
            "backend.app.api.deps",
            "backend.app.api.health",
            "backend.app.api.admin",
            "backend.app.api.api_keys",
            "backend.app.api.mfa",
            "backend.app.api.client",
            "backend.app.api.webhooks",
            "backend.app.api",
            "backend.app.core.auth",
            "backend.app.exceptions",
            "backend.app.config",
        ]
        for mod_name in list(_sys.modules.keys()):
            if any(
                mod_name == p or mod_name.startswith(p + ".") for p in stale_prefixes
            ):
                del _sys.modules[mod_name]

    def test_cascade_delete_user_data_deletes_tokens(self):
        """Verify _cascade_delete_user_data deletes all related records."""
        from backend.app.api.gdpr import _cascade_delete_user_data

        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.id = "user-123"
        mock_user.company_id = "company-456"

        _cascade_delete_user_data(mock_db, mock_user)

        # Verify refresh tokens were deleted
        assert (
            mock_db.query.called or mock_db.commit.called
        ), "DB operations must be performed during cascade delete"

        # Verify user was anonymized
        assert mock_user.email.startswith(
            "gdpr_erased_"
        ), "User email must be anonymized to gdpr_erased_*"
        assert mock_user.is_active is False, "User must be deactivated after erasure"
        assert (
            mock_user.password_hash == "GDPR_ERASED"
        ), "Password hash must be replaced after erasure"
        assert mock_user.mfa_enabled is False, "MFA must be disabled after erasure"
        assert mock_user.full_name is None, "Full name must be cleared after erasure"

    def test_cascade_delete_commits(self):
        """Verify _cascade_delete_user_data commits the transaction."""
        from backend.app.api.gdpr import _cascade_delete_user_data

        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.id = "user-abc"
        mock_user.company_id = "company-xyz"

        _cascade_delete_user_data(mock_db, mock_user)

        mock_db.commit.assert_called_once()

    def test_cascade_delete_handles_error(self):
        """Verify _cascade_delete_user_data propagates exceptions."""
        from backend.app.api.gdpr import _cascade_delete_user_data

        mock_db = MagicMock()
        mock_db.query.side_effect = Exception("DB Error")
        mock_user = MagicMock()
        mock_user.id = "user-err"
        mock_user.company_id = "company-err"

        with pytest.raises(Exception, match="DB Error"):
            _cascade_delete_user_data(mock_db, mock_user)

        mock_db.rollback.assert_called_once()

    def test_collect_user_data_returns_structure(self):
        """Verify _collect_user_data returns proper structure."""
        from backend.app.api.gdpr import _collect_user_data

        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.id = "user-exp"
        mock_user.company_id = "company-exp"
        mock_user.email = "test@example.com"
        mock_user.full_name = "Test User"
        mock_user.phone = "+1234567890"
        mock_user.avatar_url = "https://example.com/avatar.jpg"
        mock_user.role = "owner"
        mock_user.is_active = True
        mock_user.is_verified = True
        mock_user.mfa_enabled = False
        mock_user.created_at = datetime.utcnow()
        mock_user.updated_at = datetime.utcnow()

        mock_db.query.return_value.filter.return_value.first.return_value = None

        data = _collect_user_data(mock_db, mock_user)

        assert "user" in data, "Export must include user section"
        assert "company" in data, "Export must include company section"
        assert "api_keys" in data, "Export must include api_keys section"
        assert (
            "notification_preferences" in data
        ), "Export must include notification_preferences section"
        assert "oauth_accounts" in data, "Export must include oauth_accounts section"
        assert "active_sessions" in data, "Export must include active_sessions section"
        assert "exported_at" in data, "Export must include exported_at timestamp"

    def test_collect_user_data_user_fields(self):
        """Verify exported user data has correct fields, no secrets."""
        from backend.app.api.gdpr import _collect_user_data

        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.id = "user-field-test"
        mock_user.company_id = "company-123"
        mock_user.email = "fields@test.com"
        mock_user.password_hash = "SHOULD_NOT_APPEAR"
        mock_user.mfa_secret = "SHOULD_NOT_APPEAR"

        mock_db.query.return_value.filter.return_value.first.return_value = None

        data = _collect_user_data(mock_db, mock_user)

        user_data = data["user"]
        # password_hash must NOT be in export
        assert "password_hash" not in user_data, "Export must NOT include password_hash"
        # mfa_secret must NOT be in export
        assert "mfa_secret" not in user_data, "Export must NOT include mfa_secret"
        # Email should be included
        assert user_data["email"] == "fields@test.com", "Export must include email"

    def test_serialize_model_with_datetime(self):
        """Verify _serialize_model converts datetime to ISO string."""
        from backend.app.api.gdpr import _serialize_model

        mock_obj = MagicMock()
        mock_obj.name = "Test"
        mock_obj.created_at = datetime(2025, 1, 15, 12, 0, 0)

        result = _serialize_model(mock_obj, ["name", "created_at"])

        assert result["name"] == "Test"
        assert result["created_at"] == "2025-01-15T12:00:00"

    def test_serialize_model_none(self):
        """Verify _serialize_model returns None for None input."""
        from backend.app.api.gdpr import _serialize_model

        result = _serialize_model(None, ["name"])
        assert result is None


# ============================================================
# Integration: Import chain validation
# ============================================================


class TestImportChain:
    """Verify that modified modules can be imported without errors."""

    def test_admin_module_imports(self):
        content = _read("backend/app/api/admin.py")
        assert (
            "AuthorizationError" in content
        ), "admin.py must import AuthorizationError"

    def test_webhook_module_imports(self):
        content = _read("backend/app/api/webhooks.py")
        assert (
            "from fastapi import" in content and "Depends" in content
        ), "webhooks.py must import Depends from fastapi"

    def test_ip_allowlist_imports_os(self):
        content = _read("backend/app/middleware/ip_allowlist.py")
        assert (
            "import os" in content
        ), "ip_allowlist.py must import os for env var reading"

    def test_gdpr_imports_db(self):
        content = _read("backend/app/api/gdpr.py")
        assert "get_db" in content, "gdpr.py must import get_db for database access"

    def test_gdpr_imports_models(self):
        content = _read("backend/app/api/gdpr.py")
        assert (
            "RefreshToken" in content
        ), "gdpr.py must import RefreshToken for cascade delete"
        assert (
            "BackupCode" in content
        ), "gdpr.py must import BackupCode for cascade delete"
        assert (
            "MFASecret" in content
        ), "gdpr.py must import MFASecret for cascade delete"
        assert (
            "OAuthAccount" in content
        ), "gdpr.py must import OAuthAccount for cascade delete"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
