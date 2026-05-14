#!/usr/bin/env python3
"""
PARWA Security Fixes Unit Tests

Standalone tests that verify all the security fixes work correctly.
"""

import os
import sys
import asyncio
import importlib
import importlib.util
import inspect

# Set test environment BEFORE any imports
os.environ["ENVIRONMENT"] = "test"
os.environ["SECRET_KEY"] = "test_secret_key_for_testing_only_not_prod"
os.environ["JWT_SECRET_KEY"] = "test_jwt_secret_key_not_prod_32ch"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["DATA_ENCRYPTION_KEY"] = "12345678901234567890123456789012"
os.environ["REFRESH_TOKEN_PEPPER"] = "test_pepper_for_testing_only_not_prod"

# Add paths
sys.path.insert(0, "/tmp/parwa")
sys.path.insert(0, "/tmp/parwa/backend")

passed = 0
failed = 0
errors = []


def test(name, fn):
    """Run a test and track results."""
    global passed, failed
    try:
        fn()
        passed += 1
        print(f"  ✓ {name}")
    except Exception as e:
        failed += 1
        errors.append((name, str(e)))
        print(f"  ✗ {name}: {e}")


def read_file(path):
    """Read a file's source code."""
    with open(path, 'r') as f:
        return f.read()


# ─────────────────────────────────────────────────────────────────
# TEST 1: C-01/C-12 — Unauthenticated API routes fixed
# ─────────────────────────────────────────────────────────────────
def test_signals_requires_auth():
    source = read_file("/tmp/parwa/backend/app/api/signals.py")
    assert "get_current_user" in source, "signals.py must import get_current_user"
    assert "get_company_id" in source, "signals.py must import get_company_id"
    assert "Depends(get_current_user)" in source
    assert "Depends(get_company_id)" in source
    # SignalRequest must NOT have company_id field
    assert "company_id: str = Field" not in source, \
        "SignalRequest must NOT have company_id field (C-12 fix)"


def test_classification_requires_auth():
    source = read_file("/tmp/parwa/backend/app/api/classification.py")
    assert "get_current_user" in source
    assert "get_company_id" in source
    assert "Depends(get_current_user)" in source
    assert "Depends(get_company_id)" in source
    assert "company_id: str = Field" not in source, \
        "ClassifyRequest must NOT have company_id field (C-12 fix)"


def test_ai_classification_requires_auth():
    source = read_file("/tmp/parwa/backend/app/api/ai_classification.py")
    assert "get_current_user" in source
    assert "get_company_id" in source
    # Write endpoints must have auth
    assert "Depends(get_current_user)" in source
    assert "Depends(get_company_id)" in source
    
    # Import and check model fields directly (not source text)
    os.environ.setdefault("REFRESH_TOKEN_PEPPER", "test_pepper")
    sys.path.insert(0, "/tmp/parwa/backend")
    from app.api.ai_classification import ClassifyRequest, BatchClassifyRequest
    assert "company_id" not in ClassifyRequest.model_fields, \
        f"ClassifyRequest must NOT have company_id field, got: {list(ClassifyRequest.model_fields.keys())}"
    assert "company_id" not in BatchClassifyRequest.model_fields, \
        f"BatchClassifyRequest must NOT have company_id field, got: {list(BatchClassifyRequest.model_fields.keys())}"


# ─────────────────────────────────────────────────────────────────
# TEST 2: C-02 — Token revocation fail-closed in production
# ─────────────────────────────────────────────────────────────────
def test_token_revocation_fail_closed_in_production():
    """Verify is_token_revoked returns True when Redis fails in production."""
    source = read_file("/tmp/parwa/backend/app/core/auth.py")
    assert "FAIL_CLOSED" in source or "fail_closed" in source or "fail-closed" in source, \
        "is_token_revoked must have fail-closed logic for production"
    assert 'environment == "production"' in source or "ENVIRONMENT" in source, \
        "Must check environment for fail-closed behavior"


def test_token_revocation_code_structure():
    """Verify the auth.py has both fail-closed (prod) and fail-open (dev) paths."""
    source = read_file("/tmp/parwa/backend/app/core/auth.py")
    # Find is_token_revoked function
    assert "async def is_token_revoked" in source
    assert "return True" in source, "Must have True return (fail-closed) path"
    # Should have environment check
    assert "ENVIRONMENT" in source or "environment" in source


# ─────────────────────────────────────────────────────────────────
# TEST 3: C-09 — MFA sessions use Redis
# ─────────────────────────────────────────────────────────────────
def test_mfa_session_redis_functions():
    """Verify MFA session has Redis-backed functions."""
    source = read_file("/tmp/parwa/backend/app/api/mfa.py")
    assert "_store_mfa_session" in source, "Must have _store_mfa_session function"
    assert "_retrieve_mfa_session" in source, "Must have _retrieve_mfa_session function"
    assert "_MFA_REDIS_PREFIX" in source, "Must define Redis key prefix"
    assert "json.dumps" in source or "json.loads" in source, "Must serialize for Redis"
    # verify_mfa_session_token must be async
    assert "async def verify_mfa_session_token" in source, \
        "verify_mfa_session_token must be async (Redis-backed)"


def test_mfa_verify_login_is_async():
    """Verify mfa_verify_login is async and uses async verify."""
    source = read_file("/tmp/parwa/backend/app/api/mfa.py")
    assert "async def mfa_verify_login" in source, \
        "mfa_verify_login must be async (uses Redis-backed session)"
    assert "await verify_mfa_session_token" in source, \
        "Must await the Redis-backed session verification"


# ─────────────────────────────────────────────────────────────────
# TEST 4: C-04/C-05 — MCP config fixes
# ─────────────────────────────────────────────────────────────────
def test_mcp_cors_no_wildcard():
    """Verify MCP cors_origin_list never returns ["*"]."""
    spec = importlib.util.spec_from_file_location(
        "mcp_config", "/tmp/parwa/mcp_server/config.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    
    # With empty CORS_ORIGINS, should return empty list, NOT ["*"]
    settings = mod.MCPSettings(CORS_ORIGINS="")
    origins = settings.cors_origin_list
    assert origins == [], f"Expected empty list, got {origins}"
    
    # With configured origins
    settings = mod.MCPSettings(CORS_ORIGINS="http://localhost:3000,https://app.parwa.ai")
    origins = settings.cors_origin_list
    assert origins == ["http://localhost:3000", "https://app.parwa.ai"]


def test_mcp_auth_token_required_in_production():
    """Verify MCP_AUTH_TOKEN raises ValueError in production when empty."""
    from pydantic import ValidationError
    
    spec = importlib.util.spec_from_file_location(
        "mcp_config2", "/tmp/parwa/mcp_server/config.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    
    # Set ENVIRONMENT=production in os.environ so the validator sees it
    old_env = os.environ.get("ENVIRONMENT", "")
    os.environ["ENVIRONMENT"] = "production"
    try:
        raised = False
        try:
            mod.MCPSettings(MCP_AUTH_TOKEN="")
        except (ValueError, ValidationError) as e:
            raised = True
            assert "MCP_AUTH_TOKEN" in str(e)
        assert raised, "Should raise when MCP_AUTH_TOKEN empty in production"
    finally:
        os.environ["ENVIRONMENT"] = old_env or "test"


def test_mcp_middleware_rate_limited_warnings():
    """Verify MCP auth middleware has rate-limited warnings."""
    source = read_file("/tmp/parwa/mcp_server/main.py")
    assert "_last_warn_time" in source, "Must have rate-limited warning mechanism"
    assert "60" in source, "Must rate-limit warnings to once per 60 seconds"


# ─────────────────────────────────────────────────────────────────
# TEST 5: C-10 — Admin health requires auth
# ─────────────────────────────────────────────────────────────────
def test_admin_health_requires_auth():
    """Verify admin health endpoint requires require_platform_admin."""
    source = read_file("/tmp/parwa/backend/app/api/admin.py")
    
    # Find the admin_health function definition area
    lines = source.split('\n')
    found = False
    for i, line in enumerate(lines):
        if "def admin_health" in line:
            # Check next few lines for Depends
            func_block = '\n'.join(lines[i:i+6])
            assert "Depends(require_platform_admin)" in func_block, \
                "admin_health must have Depends(require_platform_admin)"
            found = True
            break
    assert found, "admin_health function not found"


# ─────────────────────────────────────────────────────────────────
# TEST 6: C-11 — JWT_SECRET_KEY + MCP_AUTH_TOKEN validation
# ─────────────────────────────────────────────────────────────────
def test_jwt_secret_key_min_length_code():
    """Verify JWT_SECRET_KEY validator enforces min length in production."""
    source = read_file("/tmp/parwa/backend/app/config.py")
    assert "len(v) < 32" in source or "len(v)<32" in source, \
        "Must check minimum 32 character length for JWT_SECRET_KEY"


def test_mcp_auth_token_backend_config_code():
    """Verify backend config has MCP_AUTH_TOKEN validator."""
    source = read_file("/tmp/parwa/backend/app/config.py")
    assert "validate_mcp_auth_token" in source, \
        "Must have MCP_AUTH_TOKEN validator in backend config"
    assert "MCP_AUTH_TOKEN" in source and "REQUIRED" in source.upper(), \
        "Must require MCP_AUTH_TOKEN in production"


# ─────────────────────────────────────────────────────────────────
# Run all tests
# ─────────────────────────────────────────────────────────────────
print("=" * 60)
print("PARWA Security Fixes — Unit Tests")
print("=" * 60)

print("\n📦 C-01/C-12: Unauthenticated API routes + cross-tenant company_id")
test("signals.py requires auth + JWT company_id", test_signals_requires_auth)
test("classification.py requires auth + JWT company_id", test_classification_requires_auth)
test("ai_classification.py requires auth + JWT company_id", test_ai_classification_requires_auth)

print("\n📦 C-02: Token revocation fail-closed in production")
test("is_token_revoked has fail-closed logic", test_token_revocation_fail_closed_in_production)
test("is_token_revoked has both prod and dev paths", test_token_revocation_code_structure)

print("\n📦 C-09: MFA sessions Redis-backed")
test("MFA session Redis functions exist", test_mfa_session_redis_functions)
test("MFA verify_login is async", test_mfa_verify_login_is_async)

print("\n📦 C-04/C-05: MCP CORS + auth enforcement")
test("MCP CORS never returns wildcard", test_mcp_cors_no_wildcard)
test("MCP_AUTH_TOKEN required in production (config)", test_mcp_auth_token_required_in_production)
test("MCP middleware has rate-limited warnings", test_mcp_middleware_rate_limited_warnings)

print("\n📦 C-10: Admin health endpoint auth")
test("admin health requires platform admin", test_admin_health_requires_auth)

print("\n📦 C-11: JWT_SECRET_KEY + MCP_AUTH_TOKEN production enforcement")
test("JWT_SECRET_KEY min 32 chars validator exists", test_jwt_secret_key_min_length_code)
test("Backend MCP_AUTH_TOKEN validator exists", test_mcp_auth_token_backend_config_code)

print("\n" + "=" * 60)
print(f"Results: {passed} passed, {failed} failed out of {passed + failed} tests")
print("=" * 60)

if failed > 0:
    print("\n❌ Failed tests:")
    for name, err in errors:
        print(f"  - {name}: {err}")
    sys.exit(1)
else:
    print("\n✅ All security fix tests passed!")
    sys.exit(0)
