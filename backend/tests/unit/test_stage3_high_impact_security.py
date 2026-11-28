"""Focused Stage 3 security contracts for high-impact historical findings.

Source-level checks avoid importing the application stack, so this file runs in
the required CI security step without external services or a live database.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _function_source(source: str, name: str):
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node, ast.get_source_segment(source, node) or ""
    raise AssertionError(f"function {name!r} not found")


def test_workflow_gsd_analytics_binds_path_tenant_to_authenticated_tenant():
    source = _read("backend/app/api/workflow.py")
    node, function = _function_source(source, "get_gsd_analytics")
    arguments = {arg.arg for arg in node.args.args + node.args.kwonlyargs}
    assert "jwt_company_id" in arguments
    assert "Depends(get_jwt_company_id)" in function
    assert "company_id != jwt_company_id" in function
    assert "AuthorizationError" in function


def test_python_rate_limiter_classifies_all_pre_auth_mfa_post_routes():
    source = _read("backend/app/core/parwa_core_bridge.py")
    _, function = _function_source(source, "classify_path")
    assert 'path.startswith("/api/auth/mfa/")' in function
    assert 'return "auth_mfa"' in function
    config_start = source.index('"auth_mfa": {')
    config_end = source.index("    },", config_start)
    assert '"scope": "ip"' in source[config_start:config_end]


def test_rust_rate_limiter_classifies_pre_auth_mfa_post_routes():
    source = _read("backend/parwa_core/src/lib.rs")
    assert 'path.starts_with("/api/auth/mfa/")' in source


def test_webhook_status_and_retry_require_platform_admin():
    source = _read("backend/app/api/webhooks.py")
    for name in ("get_webhook_status", "retry_webhook", "list_webhook_events"):
        _, function = _function_source(source, name)
        assert "Depends(require_platform_admin)" in function


def test_webhook_replay_protection_fails_closed_for_missing_or_invalid_timestamp():
    source = _read("backend/app/api/webhooks.py")
    _, function = _function_source(source, "receive_webhook")
    assert "if not occurred_at" in function
    assert "REPLAY_DETECTED" in function
    assert "except (ValueError, TypeError)" in function


def test_chat_route_requires_authoritative_authenticated_identity():
    source = _read("src/app/api/chat/route.ts")
    assert "getAuthenticatedUserId(req)" in source
    assert "status: 401" in source


def test_channel_status_never_returns_api_key_prefixes():
    source = _read("src/app/api/channel-status/route.ts")
    assert "requireAuth(request)" in source
    assert "configured: !!BREVO_API_KEY" in source
    assert "BREVO_API_KEY.slice" not in source
    assert "TWILIO_ACCOUNT_SID.slice" not in source


def test_google_id_token_is_sent_in_post_body_not_query_string():
    source = _read("backend/app/services/auth_service.py")
    _, function = _function_source(source, "_verify_google_token")
    assert 'data={"id_token": id_token}' in function
    assert "params={" not in function


def test_open_redirect_uses_local_allowlisted_paths():
    source = _read("src/lib/safe-redirect.ts")
    assert "fullyDecodeUri" in source
    assert 'decoded.startsWith("//")' in source
    assert "ALLOWED_REDIRECT_PREFIXES" in source


def test_production_registration_does_not_issue_tokens_before_email_verification():
    source = _read("backend/app/services/auth_service.py")
    _, function = _function_source(source, "register_user")
    assert "settings.is_production" in function
    assert "tokens = None" in function


def test_production_password_login_rejects_unverified_users_before_mfa_or_tokens():
    source = _read("backend/app/services/auth_service.py")
    _, function = _function_source(source, "authenticate_user")
    guard = "if get_settings().is_production and not user.is_verified"
    assert guard in function
    assert function.index(guard) < function.index("_create_token_pair")
    assert function.index(guard) < function.index("create_mfa_session_token")


def test_production_auth_dependency_rejects_unverified_legacy_tokens():
    source = _read("backend/app/api/deps.py")
    _, function = _function_source(source, "get_current_user")
    assert "get_settings().is_production and not user.is_verified" in function
    assert "Email verification required" in function


def test_google_verified_email_is_preserved_when_linking_existing_account():
    source = _read("backend/app/services/auth_service.py")
    _, function = _function_source(source, "_link_google_account")
    assert "user.is_verified = True" in function


def test_registration_bff_does_not_set_auth_cookies_without_tokens():
    source = _read("src/app/api/auth/register/route.ts")
    assert "if (tokensObj)" in source
    assert source.index("if (tokensObj)") < source.index("setAuthCookies(")


def test_production_refresh_rejects_and_revokes_unverified_user_sessions():
    source = _read("backend/app/services/auth_service.py")
    _, function = _function_source(source, "refresh_tokens")
    guard = "if get_settings().is_production and not user.is_verified"
    assert guard in function
    assert "_invalidate_all_tokens(db, stored.user_id)" in function
    assert function.index(guard) < function.index("_create_token_pair")


def test_existing_google_oauth_session_only_verifies_matching_local_email():
    source = _read("backend/app/services/auth_service.py")
    _, function = _function_source(source, "google_auth")
    assert "if not user.is_verified:" in function
    assert 'google_email != (user.email or "").lower().strip()' in function
    assert "Email verification required for this account" in function


def test_email_verification_revokes_pre_verification_refresh_sessions():
    source = _read("backend/app/services/verification_service.py")
    _, function = _function_source(source, "verify_email")
    assert "user.is_verified = True" in function
    assert "db.query(RefreshToken)" in function
    assert "RefreshToken.user_id == user.id" in function
    assert "delete(synchronize_session=False)" in function


def test_python_csrf_fallback_requires_explicit_vercel_origin_allowlist():
    source = _read("backend/app/core/parwa_core_bridge.py")
    assert "_VERCEL_PATTERN" not in source
    assert "re.match(_VERCEL_PATTERN" not in source
    assert 'check_origin == trusted or check_origin.startswith(trusted + "/")' in source


def test_rust_csrf_validator_requires_explicit_vercel_origin_allowlist():
    source = _read("backend/parwa_core/src/lib.rs")
    implementation = source.split("#[cfg(test)]", 1)[0]
    assert "vercel" not in implementation.lower()
    assert "check_origin == *trusted" in implementation
