"""PARWA Core — Rust-accelerated hot-path modules.

This package provides Rust-compiled versions of performance-critical
operations: rate limiting, circuit breaking, PII redaction, JWT auth,
and security header generation.

Usage:
    from parwa_core import (
        RateLimiter, CircuitBreakerManager, PIIRedactor,
        JWTDecoder, SecurityHeaders, CSRFValidator,
    )

    # Rate limiting
    rl = RateLimiter()
    result = rl.check_rate_limit("auth_login", "user@example.com")

    # Circuit breaking
    cb = CircuitBreakerManager()
    cb.register("google_ai", failure_threshold=3)
    if cb.is_available("google_ai"):
        result = call_google_ai(...)
        cb.record_success("google_ai")

    # PII redaction
    pii = PIIRedactor()
    matches = pii.detect_pii("SSN: 123-45-6789")
    redacted = pii.redact("Email: user@test.com", "company-123")

    # JWT
    jwt = JWTDecoder()
    payload = jwt.verify(token, secret, algorithms=["HS256"])

    # Security headers
    sec = SecurityHeaders(environment="production")
    headers = sec.generate_headers("/api/tickets")

    # CSRF
    csrf = CSRFValidator(trusted_origins=["https://app.parwa.ai"])
    csrf.is_valid_origin("https://app.parwa.ai", "")
    token = csrf.generate_csrf_token()
    csrf.validate_csrf_token(token)
"""

try:
    from parwa_core._parwa_core import (
        RateLimiter,
        CircuitBreakerManager,
        PIIRedactor,
        JWTDecoder,
        SecurityHeaders,
        CSRFValidator,
    )
    _RUST_AVAILABLE = True
except ImportError:
    _RUST_AVAILABLE = False
    RateLimiter = None
    CircuitBreakerManager = None
    PIIRedactor = None
    JWTDecoder = None
    SecurityHeaders = None
    CSRFValidator = None


def is_rust_available() -> bool:
    """Check if the Rust native module is loaded."""
    return _RUST_AVAILABLE


__all__ = [
    "RateLimiter",
    "CircuitBreakerManager",
    "PIIRedactor",
    "JWTDecoder",
    "SecurityHeaders",
    "CSRFValidator",
    "is_rust_available",
    "_RUST_AVAILABLE",
]
