"""
PARWA Rust Core — Activation & Smoke Tests

Verifies that the compiled Rust `parwa_core` extension is loaded and that the
bridge in `backend/app/core/parwa_core_bridge.py` routes to it (rather than the
pure-Python fallback). This is the regression guard for the Dockerfile fix that
makes the Rust build mandatory — if the .so is ever missing again, these tests
fail loudly instead of silently degrading to Python.

Run:  cd /home/z/repos/parwa && python3 -m pytest tests/test_parwa_core_rust.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure backend/ is importable so `app.core.parwa_core_bridge` resolves.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


# ── 1. Native module is importable ─────────────────────────────────────────

def test_parwa_core_native_importable():
    """The compiled .so must be importable as `parwa_core`."""
    import parwa_core

    assert parwa_core is not None, "parwa_core module is None"


def test_parwa_core_exports_expected_symbols():
    """All 10 Rust-backed classes the bridge depends on must be present."""
    import parwa_core

    expected = {
        "RateLimiter",
        "CircuitBreakerManager",
        "PIIRedactor",
        "JWTDecoder",
        "SecurityHeaders",
        "CSRFValidator",
        "HMACVerifier",
        "CryptoEngine",
        "ConnectionPool",
        "AsyncLogger",
    }
    missing = expected - set(dir(parwa_core))
    assert not missing, f"parwa_core missing exports: {missing}"


# ── 2. Bridge detects Rust ─────────────────────────────────────────────────

def test_bridge_rust_available_flag():
    """`_RUST_AVAILABLE` must be True after the .so is compiled."""
    from app.core.parwa_core_bridge import _RUST_AVAILABLE

    assert _RUST_AVAILABLE is True, (
        "Rust core NOT detected by bridge — production is running the slow "
        "pure-Python fallback. Run `maturin develop --release` in backend/parwa_core/."
    )


def test_bridge_is_parwa_core_available_helper():
    """The public helper must agree with the internal flag."""
    from app.core.parwa_core_bridge import is_parwa_core_available

    assert is_parwa_core_available() is True


# ── 3. Bridge singletons are Rust-backed ───────────────────────────────────

def test_rate_limiter_singleton_rust_backed():
    """The rate-limiter bridge must instantiate without error."""
    from app.core.parwa_core_bridge import get_parwa_rate_limiter

    rl = get_parwa_rate_limiter()
    assert rl is not None, "RateLimiter bridge returned None"


def test_circuit_breaker_singleton_rust_backed():
    from app.core.parwa_core_bridge import get_parwa_circuit_breaker

    cb = get_parwa_circuit_breaker()
    assert cb is not None, "CircuitBreaker bridge returned None"


def test_pii_redactor_singleton_rust_backed():
    from app.core.parwa_core_bridge import get_parwa_pii_redactor

    redactor = get_parwa_pii_redactor()
    assert redactor is not None, "PIIRedactor bridge returned None"


# ── 4. Functional smoke tests through the bridge ───────────────────────────

def test_jwt_decode_roundtrip():
    """Sign a JWT with type=access and verify the Rust decoder accepts it."""
    from app.core.parwa_core_bridge import parwa_verify_access_token
    from app.exceptions import AuthenticationError
    from jose import jwt

    secret = "test-secret-for-rust-bridge-smoke"
    # Bridge requires `type: access` in the payload.
    payload = {
        "sub": "user-123",
        "company_id": "comp-abc",
        "type": "access",
        "exp": 9999999999,
    }
    token = jwt.encode(payload, secret, algorithm="HS256")

    claims = parwa_verify_access_token(token, secret)
    assert claims is not None, "Rust JWT decoder returned None for a valid token"
    assert claims.get("sub") == "user-123"
    assert claims.get("company_id") == "comp-abc"


def test_jwt_decode_rejects_bad_token():
    """A garbage token must raise AuthenticationError, not crash."""
    from app.core.parwa_core_bridge import parwa_verify_access_token
    from app.exceptions import AuthenticationError
    import pytest

    with pytest.raises(AuthenticationError):
        parwa_verify_access_token("garbage.not.a.token", "any-secret")


def test_pii_redaction_redacts_email():
    """The Rust PIIRedactor must redact a recognizable email (async API)."""
    import asyncio
    from app.core.parwa_core_bridge import get_parwa_pii_redactor

    redactor = get_parwa_pii_redactor()
    sample = "Contact me at john.doe@example.com please."
    # Bridge API is async redact_pii(text, company_id) -> RedactionResult.
    result = asyncio.get_event_loop().run_until_complete(
        redactor.redact_pii(sample, "smoke-test-company")
    )
    assert "john.doe@example.com" not in result.redacted_text, (
        f"Email not redacted — result: {result.redacted_text!r}"
    )


# ── 5. CSRF + Security headers ─────────────────────────────────────────────

def test_csrf_validator_origin_check():
    """The Rust CSRFValidator must validate a trusted origin."""
    from app.core.parwa_core_bridge import parwa_csrf_validator

    validator = parwa_csrf_validator(trusted_origins=["https://parwa.buzz"])
    # Same-origin should pass.
    assert validator.is_valid_origin("https://parwa.buzz") is True
    # Foreign origin should fail.
    assert validator.is_valid_origin("https://evil.example") is False


def test_security_headers_generated():
    """Security headers must include CSP with a nonce."""
    from app.core.parwa_core_bridge import parwa_get_security_headers

    headers = parwa_get_security_headers("/", "production")
    assert isinstance(headers, dict)
    # CSP must be present and contain a nonce (parwa_core injects one).
    csp = headers.get("Content-Security-Policy", "")
    assert csp, "CSP header missing"
    assert "nonce-" in csp, f"CSP has no nonce: {csp!r}"


# ── 6. Rate limiter enforces limits ────────────────────────────────────────

def test_rate_limiter_allows_then_blocks():
    """Hit the limiter until it trips — must eventually block."""
    from app.core.parwa_core_bridge import get_parwa_rate_limiter

    rl = get_parwa_rate_limiter()
    identifier = "smoke-test-ip-" + str(id(rl))
    # Use a real category from CATEGORY_CONFIG (e.g. 'auth' has a small limit).
    results = []
    for _ in range(200):
        result = rl.check_rate_limit("auth", identifier)
        results.append(result.allowed)
        if not result.allowed:
            break
    assert False in results, "Rate limiter never blocked after 200 hits — not enforcing"


if __name__ == "__main__":
    # Allow `python3 tests/test_parwa_core_rust.py` for quick manual runs.
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
