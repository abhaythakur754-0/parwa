"""
PARWA AI — Per-Provider Webhook Signature Verification

Provides a pluggable verification system that routes signature checks
to the correct verification method for each provider. This replaces
the monolithic if/elif chain in the webhook API route.

Supports:
  - HMAC-SHA256 (Paddle, Shopify, Stripe, custom)
  - URL+params signature (Twilio)
  - IP allowlist (Brevo)
  - Raw secret comparison (simple/custom providers)

New providers can register their own verifier without modifying
existing code.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any, Callable, Dict, Optional, Protocol

from fastapi import Request

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Verifier Protocol
# ---------------------------------------------------------------------------

class WebhookVerifier(Protocol):
    """Protocol that every webhook verifier must satisfy.

    Returns True if the signature/IP/auth checks pass, False otherwise.
    """

    def __call__(
        self,
        request: Request,
        payload: dict,
        body: bytes,
        secret: str,
    ) -> bool: ...


# ---------------------------------------------------------------------------
# Built-in Verifiers
# ---------------------------------------------------------------------------

def verify_hmac_sha256(
    request: Request,
    payload: dict,
    body: bytes,
    secret: str,
    header_name: str = "x-signature",
) -> bool:
    """Verify HMAC-SHA256 signature from a request header.

    Computes HMAC-SHA256 of the raw body with the given secret and
    compares it against the value in the specified header.

    Args:
        request:     FastAPI Request object.
        payload:     Parsed JSON payload (unused for HMAC, kept for protocol).
        body:        Raw request body bytes.
        secret:      Shared secret key.
        header_name: Header containing the signature.

    Returns:
        True if the signature matches.
    """
    if not secret:
        logger.warning("verify_hmac_sha256: empty secret — rejecting")
        return False

    received = request.headers.get(header_name, "")
    if not received:
        logger.warning(
            "verify_hmac_sha256: missing header '%s'", header_name,
        )
        return False

    expected = hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, received)


def verify_paddle(
    request: Request,
    payload: dict,
    body: bytes,
    secret: str,
) -> bool:
    """Verify Paddle webhook signature (HMAC-SHA256).

    Paddle sends the signature in the ``paddle-signature`` header.
    The signature is computed as HMAC-SHA256(secret, raw_body).
    """
    return verify_hmac_sha256(
        request, payload, body, secret,
        header_name="paddle-signature",
    )


def verify_shopify(
    request: Request,
    payload: dict,
    body: bytes,
    secret: str,
) -> bool:
    """Verify Shopify webhook signature (HMAC-SHA256).

    Shopify sends the signature in the ``x-shopify-hmac-sha256`` header
    as a Base64-encoded HMAC-SHA256 digest.
    """
    import base64

    if not secret:
        logger.warning("verify_shopify: empty secret — rejecting")
        return False

    received = request.headers.get("x-shopify-hmac-sha256", "")
    if not received:
        logger.warning("verify_shopify: missing x-shopify-hmac-sha256 header")
        return False

    expected = base64.b64encode(
        hmac.new(
            secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).digest(),
    ).decode("utf-8")

    return hmac.compare_digest(expected, received)


def verify_twilio(
    request: Request,
    payload: dict,
    body: bytes,
    secret: str,
) -> bool:
    """Verify Twilio webhook signature.

    Twilio signs the URL + sorted POST params with the auth token.
    The signature is sent in the ``x-twilio-signature`` header.
    """
    if not secret:
        logger.warning("verify_twilio: empty auth token — rejecting")
        return False

    signature = request.headers.get("x-twilio-signature", "")
    if not signature:
        logger.warning("verify_twilio: missing x-twilio-signature header")
        return False

    # Build the data string: URL + sorted params
    url = str(request.url)
    data = url
    if payload:
        for key in sorted(payload.keys()):
            data += key + str(payload[key])

    expected = base64.b64encode(
        hmac.new(
            secret.encode("utf-8"),
            data.encode("utf-8"),
            hashlib.sha1,
        ).digest(),
    ).decode("utf-8")

    import base64
    return hmac.compare_digest(expected, signature)


def verify_brevo_ip(
    request: Request,
    payload: dict,
    body: bytes,
    secret: str,
) -> bool:
    """Verify Brevo webhook by IP allowlist.

    Brevo doesn't use HMAC — they use IP-based verification.
    The ``secret`` parameter here is a comma-separated list of allowed IPs/CIDRs.
    If ``secret`` is empty, we use the default Brevo inbound IPs.
    """
    import ipaddress

    # Default Brevo inbound IPs (from their documentation)
    DEFAULT_BREVO_IPS = [
        "185.107.232.0/24",
        "77.32.224.0/24",
        "51.15.224.0/24",
        "217.115.112.0/20",
    ]

    if secret:
        allowed = [cidr.strip() for cidr in secret.split(",") if cidr.strip()]
    else:
        allowed = DEFAULT_BREVO_IPS

    # Get client IP
    forwarded = request.headers.get("x-forwarded-for", "")
    client_ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (request.client.host if request.client else "")
    )

    if not client_ip:
        logger.warning("verify_brevo_ip: cannot determine client IP")
        return False

    try:
        client = ipaddress.ip_address(client_ip)
        for network_str in allowed:
            try:
                network = ipaddress.ip_network(network_str, strict=False)
                if client in network:
                    return True
            except ValueError:
                # Single IP, not a CIDR
                if client_ip == network_str:
                    return True
    except ValueError:
        logger.warning("verify_brevo_ip: invalid client IP '%s'", client_ip)
        return False

    logger.warning("verify_brevo_ip: client IP '%s' not in allowlist", client_ip)
    return False


def verify_generic(
    request: Request,
    payload: dict,
    body: bytes,
    secret: str,
) -> bool:
    """Generic fallback verifier for custom/unregistered providers.

    Attempts:
      1. x-signature header (HMAC-SHA256)
      2. x-webhook-secret header (direct comparison)
      3. If no secret configured, reject (fail-closed).
    """
    if not secret:
        # Fail-closed: no secret = no verification possible
        logger.warning("verify_generic: no secret configured — rejecting")
        return False

    # Try HMAC-SHA256 first
    sig_header = request.headers.get("x-signature", "")
    if sig_header:
        expected = hmac.new(
            secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()
        if hmac.compare_digest(expected, sig_header):
            return True

    # Try direct secret comparison (simple webhook providers)
    secret_header = request.headers.get("x-webhook-secret", "")
    if secret_header:
        return hmac.compare_digest(secret, secret_header)

    logger.warning("verify_generic: no valid signature header found")
    return False


# ---------------------------------------------------------------------------
# Verifier Registry
# ---------------------------------------------------------------------------

class WebhookVerifierRegistry:
    """Central registry for webhook signature verifiers.

    Usage::

        WebhookVerifierRegistry.register("stripe", verify_stripe)
        is_valid = WebhookVerifierRegistry.verify("stripe", request, payload, body, secret)
    """

    _verifiers: Dict[str, WebhookVerifier] = {}

    @classmethod
    def register(cls, provider: str, verifier: WebhookVerifier) -> None:
        """Register a verifier for a provider.

        Args:
            provider:  Unique provider key (e.g. ``"stripe"``).
            verifier:  Callable conforming to the WebhookVerifier protocol.
        """
        provider = provider.lower().strip()
        if provider in cls._verifiers:
            logger.warning(
                "Overwriting existing webhook verifier for provider '%s'",
                provider,
            )
        cls._verifiers[provider] = verifier
        logger.debug("Registered webhook verifier for provider '%s'", provider)

    @classmethod
    def verify(
        cls,
        provider: str,
        request: Request,
        payload: dict,
        body: bytes,
        secret: str,
    ) -> bool:
        """Verify a webhook request using the registered verifier.

        Falls back to ``verify_generic`` if the provider has no
        registered verifier.

        Args:
            provider: Provider name.
            request:  FastAPI Request object.
            payload:  Parsed JSON payload.
            body:     Raw request body bytes.
            secret:   Provider-specific secret/key.

        Returns:
            True if verification passes.
        """
        provider = provider.lower().strip()
        verifier = cls._verifiers.get(provider, verify_generic)
        try:
            result = verifier(request, payload, body, secret)
            if not result:
                logger.warning(
                    "Webhook signature verification failed for provider '%s'",
                    provider,
                )
            return result
        except Exception as exc:
            logger.error(
                "Webhook verifier error for provider '%s': %s",
                provider,
                exc,
            )
            return False

    @classmethod
    def get_verifier(cls, provider: str) -> Optional[WebhookVerifier]:
        """Return the verifier for a provider, or None."""
        return cls._verifiers.get(provider.lower().strip())

    @classmethod
    def list_providers(cls) -> list[str]:
        """Return all registered provider names with verifiers."""
        return sorted(cls._verifiers.keys())

    @classmethod
    def has_verifier(cls, provider: str) -> bool:
        """Check if a provider has a registered verifier."""
        return provider.lower().strip() in cls._verifiers


# ---------------------------------------------------------------------------
# Auto-register built-in verifiers
# ---------------------------------------------------------------------------

def _register_defaults():
    """Register all built-in webhook verifiers."""
    WebhookVerifierRegistry.register("paddle", verify_paddle)
    WebhookVerifierRegistry.register("shopify", verify_shopify)
    WebhookVerifierRegistry.register("twilio", verify_twilio)
    WebhookVerifierRegistry.register("brevo", verify_brevo_ip)


_register_defaults()
