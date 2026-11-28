"""Focused regression contracts for pre-authentication MFA login enforcement."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICE = ast.parse((ROOT / "app/services/auth_service.py").read_text(encoding="utf-8"))
AUTH_API = ast.parse((ROOT / "app/api/auth.py").read_text(encoding="utf-8"))
MFA_API = ast.parse((ROOT / "app/api/mfa.py").read_text(encoding="utf-8"))
SCHEMA = ast.parse((ROOT / "app/schemas/mfa.py").read_text(encoding="utf-8"))


def _function(tree, name):
    return next(n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)


def _calls(node, name):
    return [n for n in ast.walk(node) if isinstance(n, ast.Call) and ast.unparse(n.func) == name]


def test_password_login_issues_pre_auth_challenge_before_any_tokens():
    login = _function(SERVICE, "authenticate_user")
    branch = next(n for n in ast.walk(login) if isinstance(n, ast.If) and ast.unparse(n.test) == "user.mfa_enabled")
    assert _calls(branch, "create_mfa_session_token")
    assert any(isinstance(n, ast.Return) and isinstance(n.value, ast.Dict) and
               any(isinstance(k, ast.Constant) and k.value == "mfa_required" for k in n.value.keys)
               for n in ast.walk(branch))
    token_line = next(n.lineno for n in ast.walk(login) if isinstance(n, ast.Call) and ast.unparse(n.func) == "_create_token_pair")
    assert branch.lineno < token_line


def test_auth_endpoint_returns_challenge_without_setting_auth_cookies():
    login = _function(AUTH_API, "login")
    assert any(isinstance(n, ast.If) and "mfa_required" in ast.unparse(n.test) for n in ast.walk(login))
    assert len(_calls(login, "_set_token_cookies")) == 1


def test_totp_success_uses_standard_token_pair_and_tenant_bound_user():
    verify = _function(MFA_API, "mfa_verify_login")
    assert _calls(verify, "verify_mfa_session_token")
    assert any(isinstance(n, ast.Attribute) and n.attr == "company_id" for n in ast.walk(verify))
    assert any(isinstance(n, ast.If) and "status" in ast.unparse(n.test) and "verified" in ast.unparse(n.test)
               for n in ast.walk(verify))
    assert _calls(_function(MFA_API, "_issue_mfa_login_response"), "_create_token_pair")


def test_google_oauth_existing_mfa_accounts_also_require_challenge():
    google_auth = _function(SERVICE, "google_auth")
    assert isinstance(google_auth, ast.AsyncFunctionDef)
    mfa_branches = [n for n in ast.walk(google_auth) if isinstance(n, ast.If) and ast.unparse(n.test) == "user.mfa_enabled"]
    assert len(mfa_branches) >= 2, "both linked Google and existing-email accounts must enforce MFA"
    assert all(_calls(branch, "create_mfa_session_token") for branch in mfa_branches)
    google_route = _function(AUTH_API, "google_login")
    assert _calls(google_route, "google_auth") == []
    assert any(isinstance(n, ast.Await) and isinstance(n.value, ast.Call) and ast.unparse(n.value.func) == "google_auth" for n in ast.walk(google_route))
    assert len(_calls(google_route, "_set_token_cookies")) == 1


def test_backup_login_requires_pre_auth_session_and_single_use_code():
    verify = _function(MFA_API, "mfa_backup_login_verify")
    assert _calls(verify, "verify_mfa_session_token")
    assert _calls(verify, "use_backup_code")
    assert _calls(verify, "_issue_mfa_login_response")
    assert any(isinstance(n, ast.ClassDef) and n.name == "MFABackupLoginVerifyRequest" for n in SCHEMA.body)


def test_frontend_uses_matching_routes_and_sets_http_only_auth_cookies():
    root = ROOT.parent
    login_route = (root / "src/app/api/auth/login/route.ts").read_text(encoding="utf-8")
    login_page = (root / "src/app/(auth)/login/page.tsx").read_text(encoding="utf-8")
    google_route = (root / "src/app/api/auth/google/route.ts").read_text(encoding="utf-8")
    store = (root / "src/lib/mfa-store.ts").read_text(encoding="utf-8")
    proxy = (root / "src/app/api/mfa/[...path]/route.ts").read_text(encoding="utf-8")
    assert 'status: "mfa_required"' in login_route and 'status: "mfa_required"' in google_route
    assert "result.status === 'mfa_required'" in login_page
    assert "sessionStorage.setItem('parwa_mfa_session_token'" in login_page
    assert "${API_BASE}/verify" in store and "${API_BASE}/backup/verify" in store
    assert "mfa_session_token: mfaSessionToken" in store
    assert "setAuthCookies(" in proxy and "data.access_token" in proxy and "data.refresh_token" in proxy
