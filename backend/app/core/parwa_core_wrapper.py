"""
PARWA Core Wrapper — Convenience imports for middleware integration.

Import this in middleware files to use Rust-accelerated functions:

    from app.core.parwa_core_wrapper import (
        parwa_rate_limiter,
        parwa_circuit_breaker,
        parwa_pii_redactor,
        parwa_verify_access_token,
        parwa_get_security_headers,
        parwa_csrf_validator,
        is_parwa_core_available,
        get_bridge_diagnostics,
    )
"""

from app.core.parwa_core_bridge import (
    # Availability
    is_parwa_core_available,
    # Factory singletons
    get_parwa_rate_limiter,
    get_parwa_circuit_breaker,
    get_parwa_pii_redactor,
    parwa_csrf_validator,
    # Standalone functions
    parwa_verify_access_token,
    parwa_get_unverified_claims,
    parwa_get_security_headers,
    # Data classes
    RateLimitResult,
    PIIMatch,
    RedactionResult,
    # Diagnostics
    get_bridge_diagnostics,
    # Config
    CATEGORY_CONFIG,
)

# Pre-initialised singleton instances for middleware convenience
parwa_rate_limiter = get_parwa_rate_limiter()
parwa_circuit_breaker = get_parwa_circuit_breaker()
parwa_pii_redactor = get_parwa_pii_redactor()

# Back-compat aliases (from old bridge API names)
is_rust_loaded = is_parwa_core_available
get_diagnostics = get_bridge_diagnostics
get_security_headers = parwa_get_security_headers
generate_nonce = parwa_csrf_validator().generate_csrf_token


def verify_origin(origin: str, allowed_origins: list) -> bool:
    """Quick origin check using the CSRF validator bridge."""
    validator = parwa_csrf_validator(trusted_origins=allowed_origins)
    return validator.is_valid_origin(origin)


__all__ = [
    # New API
    "is_parwa_core_available",
    "get_parwa_rate_limiter",
    "get_parwa_circuit_breaker",
    "get_parwa_pii_redactor",
    "parwa_csrf_validator",
    "parwa_verify_access_token",
    "parwa_get_unverified_claims",
    "parwa_get_security_headers",
    "RateLimitResult",
    "PIIMatch",
    "RedactionResult",
    "get_bridge_diagnostics",
    "CATEGORY_CONFIG",
    # Pre-built singletons
    "parwa_rate_limiter",
    "parwa_circuit_breaker",
    "parwa_pii_redactor",
    # Back-compat aliases
    "is_rust_loaded",
    "get_diagnostics",
    "get_security_headers",
    "generate_nonce",
    "verify_origin",
]
