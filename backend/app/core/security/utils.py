"""
PARWA — Shared Client IP Extraction Utility

Centralises IP extraction logic so all middleware (rate limiter,
IP allowlist, request logger) use a single, consistent implementation.

H-06: All middleware MUST use ``get_client_ip`` instead of duplicating
this logic.  The function honours the ``TRUSTED_PROXY_COUNT`` environment
variable (default ``1``) which indicates how many reverse-proxy layers
sit in front of the application.

IP resolution order:
    1. ``X-Forwarded-For`` — rightmost N addresses (based on
       ``TRUSTED_PROXY_COUNT``) are trusted.
    2. ``X-Real-IP`` — single-hop proxy fallback.
    3. ``request.client.host`` / ``scope[\"client\"][0]`` — direct
       connection fallback.
"""

import os
from typing import Union

from starlette.requests import Request

_TRUSTED_PROXY_COUNT = int(os.getenv("TRUSTED_PROXY_COUNT", "1"))


def get_client_ip(request_or_scope: Union[Request, dict]) -> str:
    """Extract the real client IP from a Starlette Request or ASGI scope.

    Parameters
    ----------
    request_or_scope:
        A :class:`starlette.requests.Request` instance **or** a raw
        ``scope`` dict (for pure-ASGI middleware).

    Returns
    -------
    str
        The resolved client IP, or ``\"unknown\"`` when it cannot be
        determined.
    """
    # ── Normalise input ────────────────────────────────────────
    if isinstance(request_or_scope, Request):
        return _from_starlette_request(request_or_scope)

    # ASGI scope dict
    return _from_asgi_scope(request_or_scope)


# ────────────────────────────────────────────────────────────────
# Internal helpers
# ────────────────────────────────────────────────────────────────

def _from_starlette_request(request: Request) -> str:
    """Resolve IP from a Starlette :class:`Request`."""
    # 1. X-Forwarded-For
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded and _TRUSTED_PROXY_COUNT > 0:
        ips = [ip.strip() for ip in forwarded.split(",")]
        if len(ips) >= _TRUSTED_PROXY_COUNT:
            return ips[-_TRUSTED_PROXY_COUNT]

    # 2. X-Real-IP
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # 3. Direct connection
    if request.client:
        return request.client.host

    return "unknown"


def _from_asgi_scope(scope: dict) -> str:
    """Resolve IP from a raw ASGI scope dict."""
    headers = dict(scope.get("headers", []))

    # 1. X-Forwarded-For
    forwarded = headers.get(b"x-forwarded-for", b"").decode(
        "utf-8", errors="ignore"
    )
    if forwarded and _TRUSTED_PROXY_COUNT > 0:
        ips = [ip.strip() for ip in forwarded.split(",")]
        if len(ips) >= _TRUSTED_PROXY_COUNT:
            return ips[-_TRUSTED_PROXY_COUNT]

    # 2. X-Real-IP
    real_ip = headers.get(b"x-real-ip", b"").decode(
        "utf-8", errors="ignore"
    )
    if real_ip:
        return real_ip.strip()

    # 3. Direct connection
    client = scope.get("client")
    if client:
        return client[0]

    return ""
