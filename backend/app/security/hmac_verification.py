"""
HMAC Signature Verification (BC-011, BC-003)

Provides webhook signature verification for third-party providers:
- Paddle (HMAC-SHA256)
- Twilio (RFC 5849)
- Shopify (HMAC-SHA256)
- Brevo (IP allowlist)

BC-011: All comparisons use hmac.compare_digest (constant-time).
Fail-closed design: returns False on ANY error.
"""

import hashlib
import hmac
import ipaddress


# Default Brevo IP ranges (from Brevo documentation)
DEFAULT_BREVO_IPS = [
    "185.107.232.0/24",
    "102.134.48.0/24",
    "1.179.106.0/24",
    "185.107.236.0/24",
]


def verify_paddle_signature(
    payload_body: bytes,
    signature_header: str,
    secret: str,
) -> bool:
    """Verify Paddle webhook HMAC-SHA256 signature.

    Paddle signs webhook payloads with HMAC-SHA256 using the
    webhook secret. The signature is passed as a hex string.

    Args:
        payload_body: Raw request body bytes.
        signature_header: The Paddle signature header value.
        secret: Paddle webhook signing secret.

    Returns:
        True if signature is valid, False otherwise.
    """
    if not payload_body or not signature_header or not secret:
        return False
    try:
        expected = hmac.new(
            secret.encode("utf-8"),
            payload_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(
            expected, signature_header.strip(),
        )
    except Exception:
        return False


def verify_twilio_signature(
    url: str,
    params: dict,
    twilio_signature: str,
    auth_token: str,
) -> bool:
    """Verify Twilio webhook signature (RFC 5849).

    Twilio concatenates the URL and sorted parameters into a
    signature string, then signs with HMAC-SHA1.

    Args:
        url: The full URL of the webhook endpoint.
        params: Dictionary of request parameters (form data).
        twilio_signature: The X-Twilio-Signature header value.
        auth_token: Twilio auth token for signing.

    Returns:
        True if signature is valid, False otherwise.
    """
    if not url or not params or not twilio_signature or not auth_token:
        return False
    try:
        # Sort params and concatenate as key=value pairs
        sorted_params = sorted(params.items())
        data = url
        for key, value in sorted_params:
            data += key + str(value)

        expected = hmac.new(
            auth_token.encode("utf-8"),
            data.encode("utf-8"),
            hashlib.sha1,
        ).hexdigest()

        return hmac.compare_digest(
            expected, twilio_signature.strip(),
        )
    except Exception:
        return False


def verify_shopify_hmac(
    payload_body: bytes,
    hmac_header: str,
    secret: str,
) -> bool:
    """Verify Shopify webhook HMAC-SHA256 signature.

    Shopify signs webhook payloads with HMAC-SHA256 using the
    app secret. The signature is passed as a base64 string.

    Args:
        payload_body: Raw request body bytes.
        hmac_header: The X-Shopify-Hmac-Sha256 header value.
        secret: Shopify app client secret.

    Returns:
        True if HMAC is valid, False otherwise.
    """
    if not payload_body or not hmac_header or not secret:
        return False
    try:
        import base64
        expected = hmac.new(
            secret.encode("utf-8"),
            payload_body,
            hashlib.sha256,
        ).digest()
        expected_b64 = base64.b64encode(expected).decode("utf-8")
        return hmac.compare_digest(
            expected_b64, hmac_header.strip(),
        )
    except Exception:
        return False


def verify_brevo_ip(
    client_ip: str,
    allowed_ips: list = None,
) -> bool:
    """Verify client IP is in Brevo allowlist.

    Brevo uses IP allowlisting instead of HMAC signatures.
    Checks if the client IP falls within any of the
    allowed CIDR ranges.

    Args:
        client_ip: The client's IP address string.
        allowed_ips: List of CIDR strings. Uses default
            Brevo IPs if None.

    Returns:
        True if IP is allowed, False otherwise.
    """
    if not client_ip:
        return False
    try:
        ips = allowed_ips if allowed_ips is not None else DEFAULT_BREVO_IPS
        ip_obj = ipaddress.ip_address(client_ip.strip())
        for cidr in ips:
            try:
                if ip_obj in ipaddress.ip_network(cidr, strict=False):
                    return True
            except Exception:
                continue
        return False
    except Exception:
        return False
