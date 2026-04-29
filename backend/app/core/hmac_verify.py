"""
HMAC Verification Utility (BC-003, BC-011)

DEPRECATED: This module is a thin wrapper around the canonical
implementation in backend.app.security.hmac_verification.

All new code should import from:
    backend.app.security.hmac_verification

This module is kept for backward compatibility only.
"""

from app.security.hmac_verification import (
    verify_brevo_ip,
    verify_paddle_signature,
    verify_shopify_hmac,
    verify_twilio_signature,
)

# Alias — kept as the SAME object so identity checks (is) pass
verify_shopify_signature = verify_shopify_hmac

__all__ = [
    "verify_paddle_signature",
    "verify_twilio_signature",
    "verify_shopify_hmac",
    "verify_shopify_signature",
    "verify_brevo_ip",
]


def verify_hmac_signature(
    payload_bytes: bytes,
    signature: str,
    secret: str,
    hash_algorithm: str = "sha256",
) -> bool:
    """Generic HMAC verification with constant-time comparison.

    Delegates to verify_paddle_signature for hex-encoded HMAC-SHA256.
    """
    import hashlib

    if not payload_bytes or not signature or not secret:
        return False
    try:
        hash_func = getattr(hashlib, hash_algorithm, None)
        if hash_func is None:
            return False
        import hmac as hmac_mod

        expected = hmac_mod.new(
            secret.encode("utf-8"),
            payload_bytes,
            hash_func,
        ).hexdigest()
        return hmac_mod.compare_digest(
            expected,
            signature.strip(),
        )
    except Exception:
        return False
