"""
PARWA Variant Check Middleware (BC-001 / BC-007)

Pure ASGI middleware that enforces variant resource limits on API routes.
When a limit is exceeded, returns a 402 Payment Required response with
usage details and an upgrade URL.

Intercepted routes (POST only):
    - POST /api/v1/tickets        -> check ticket limit
    - POST /api/v1/team/invite    -> check team member limit
    - POST /api/v1/agents         -> check AI agent limit
    - POST /api/v1/kb/documents   -> check knowledge-base doc limit

Skipped routes:
    - Health / readiness endpoints
    - Auth endpoints
    - Billing endpoints
    - Webhook endpoints
    - Non-POST requests (GET, DELETE, OPTIONS, etc.)

Building Codes:
    - BC-001: Multi-Tenant Isolation (company_id on every check)
    - BC-007: AI Model Interaction (resource gating per variant tier)
"""

import json
import logging
from typing import Callable, Dict, List, Optional
from uuid import UUID

from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("parwa.middleware.variant_check")

# ── Configuration ──────────────────────────────────────────────────────

# Route prefix -> limit_type mapping
# Only POST requests to these prefixes are checked.
ROUTE_LIMITS: Dict[str, str] = {
    "/api/v1/tickets": "tickets",
    "/api/v1/team/invite": "team_members",
    "/api/v1/agents": "ai_agents",
    "/api/v1/kb/documents": "kb_docs",
}

# Paths that are always skipped (exact match)
SKIP_PATHS = {
    "/health",
    "/health/detail",
    "/ready",
    "/metrics",
}

# Path prefixes that are always skipped
SKIP_PREFIXES: List[str] = [
    "/health",
    "/ready",
    "/metrics",
    "/auth/",
    "/api/v1/auth/",
    "/api/v1/billing/",
    "/webhooks/",
    "/api/v1/webhooks/",
]

# HTTP methods that should skip the check (read-only or CORS preflight)
SKIP_METHODS = {"GET", "DELETE", "HEAD", "OPTIONS", "PATCH"}

# Header name for company ID
COMPANY_ID_HEADER = "X-Company-ID"

# Default upgrade URL included in 402 responses
DEFAULT_UPGRADE_URL = "/billing/upgrade"


# ── Middleware ──────────────────────────────────────────────────────────


class VariantCheckMiddleware:
    """Pure ASGI middleware for variant resource-limit enforcement.

    Inspects every HTTP request and, for POST routes that consume
    variant resources (tickets, team invites, agents, KB docs),
    calls ``VariantLimitService`` to verify the company is within
    its tier limits.  When a limit is exceeded a ``402 Payment
    Required`` JSON response is returned immediately.

    Must be registered *after* TenantMiddleware (so that
    ``company_id`` is available via ``request.state`` or the
    ``X-Company-ID`` header) but before the main application
    routes.
    """

    def __init__(self, app: Callable):
        """Wrap an ASGI *app* with variant-limit checking.

        Args:
            app: The downstream ASGI application.
        """
        self.app = app

    # ── ASGI entry point ───────────────────────────────────────────

    async def __call__(self, scope: dict, receive: Callable, send: Callable):
        """Process a single ASGI HTTP request through the middleware."""
        # Pass non-HTTP scopes (lifespan, websocket) through unchanged
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        method: str = scope.get("method", "").upper()
        path: str = scope.get("path", "")

        # ── Fast-path: skip non-POST and excluded paths ──
        if method != "POST" or self._should_skip(path):
            await self.app(scope, receive, send)
            return

        # ── Determine which limit to check (if any) ──
        limit_type = self._get_limit_type(path)
        if not limit_type:
            await self.app(scope, receive, send)
            return

        # ── Extract company_id ──
        company_id = self._extract_company_id(scope)
        if not company_id:
            # Unauthenticated request — let auth middleware handle it
            await self.app(scope, receive, send)
            return

        # ── Check the limit ──
        result = await self._check_limit(company_id, limit_type)

        if not result.get("allowed", True):
            # Service error (unable to verify) → 503 Service Unavailable
            if result.get("error") and not result.get("limit"):
                logger.error(
                    "variant_check_service_error company_id=%s limit_type=%s error=%s path=%s",
                    company_id,
                    limit_type,
                    result.get("error"),
                    path,
                )
                response = JSONResponse(
                    status_code=503,
                    content={
                        "error": result.get("error"),
                        "message": result.get("error"),
                    },
                )
                await response(scope, receive, send)
                return

            # Limit exceeded → 402 Payment Required
            logger.info(
                "variant_limit_exceeded company_id=%s limit_type=%s "
                "current_usage=%s limit=%s path=%s",
                company_id,
                limit_type,
                result.get("current_usage"),
                result.get("limit"),
                path,
            )

            response = JSONResponse(
                status_code=402,
                content={
                    "error": "variant_limit_exceeded",
                    "message": result.get(
                        "message",
                        f"You have reached your {limit_type} limit",
                    ),
                    "current_usage": result.get("current_usage", 0),
                    "limit": result.get("limit", 0),
                    "overage_rate": result.get(
                        "overage_rate", "$0.10/ticket",
                    ),
                    "upgrade_url": DEFAULT_UPGRADE_URL,
                },
            )
            await response(scope, receive, send)
            return

        # ── Limit OK — proceed downstream ──
        await self.app(scope, receive, send)

    # ── Helper methods ─────────────────────────────────────────────

    @staticmethod
    def _should_skip(path: str) -> bool:
        """Return *True* if *path* should bypass the limit check.

        Matches against the exact-skip set and the skip-prefix list.
        """
        if path in SKIP_PATHS:
            return True
        for prefix in SKIP_PREFIXES:
            if path.startswith(prefix):
                return True
        return False

    @staticmethod
    def _get_limit_type(path: str) -> Optional[str]:
        """Map a request *path* to a variant-limit type.

        Only POST routes listed in ``ROUTE_LIMITS`` are recognised.
        Returns ``None`` for unmatched paths.
        """
        for route_prefix, limit_type in ROUTE_LIMITS.items():
            if path.startswith(route_prefix):
                return limit_type
        return None

    @staticmethod
    def _extract_company_id(scope: dict) -> Optional[str]:
        """Extract ``company_id`` from the ASGI *scope*.

        Lookup order:
        1. ``X-Company-ID`` request header
        2. JWT bearer token claims (``company_id`` claim)

        Returns ``None`` when neither source provides a usable value.
        """
        headers = dict(scope.get("headers", []))

        # 1. Check X-Company-ID header
        raw_header = headers.get(b"x-company-id", b"").decode("utf-8", errors="ignore").strip()
        if raw_header:
            return raw_header

        # 2. Check Authorization header for JWT
        auth_header = headers.get(b"authorization", b"").decode("utf-8", errors="ignore").strip()
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
            company_id = VariantCheckMiddleware._decode_company_id_from_jwt(token)
            if company_id:
                return company_id

        return None

    @staticmethod
    def _decode_company_id_from_jwt(token: str) -> Optional[str]:
        """Decode ``company_id`` claim from a JWT token without verification.

        This is intentional — the middleware only needs the claim for the
        limit lookup.  Authentication/verification is handled by the auth
        middleware or route-level dependency.

        Returns ``None`` if the token is malformed or missing the claim.
        """
        import base64

        try:
            # JWT structure: header.payload.signature (dot-separated)
            parts = token.split(".")
            if len(parts) != 3:
                return None

            # Decode the payload (second segment)
            payload_b64 = parts[1]
            # Add padding if necessary
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += "=" * padding

            payload_json = base64.urlsafe_b64decode(payload_b64)
            payload = json.loads(payload_json)

            company_id = payload.get("company_id")
            if company_id and isinstance(company_id, str) and company_id.strip():
                return company_id.strip()

            return None
        except Exception:
            logger.debug(
                "variant_check_jwt_decode_failed",
                exc_info=False,
            )
            return None

    @staticmethod
    async def _check_limit(company_id: str, limit_type: str) -> dict:
        """Check variant resource limits via ``VariantLimitService``.

        For ``tickets`` the full usage-vs-limit check is performed.
        For other limit types (team_members, ai_agents, kb_docs) the
        check is delegated to ``enforce_limit`` on the service layer.

        The method is **fail-closed**: on any service error the request
        is blocked with a 503 status so that a transient service failure
        never allows unchecked resource consumption.

        Args:
            company_id: The tenant's company identifier.
            limit_type: One of ``tickets``, ``team_members``,
                        ``ai_agents``, ``kb_docs``.

        Returns:
            ``{"allowed": True}`` when within limits, or
            ``{"allowed": False, "message": ..., "current_usage": ...,
              "limit": ...}`` when the limit has been exceeded, or
            ``{"allowed": False, "error": ...}`` when verification fails.
        """
        if limit_type != "tickets":
            # Enforce all resource limits, not just tickets
            from app.services.variant_limit_service import get_variant_limit_service
            limit_service = get_variant_limit_service()
            try:
                result = limit_service.enforce_limit(company_id, limit_type)
                return result  # Returns {"allowed": True} on success
            except Exception as limit_err:
                logger.error("variant_check_enforcement_failed limit_type=%s error=%s", limit_type, str(limit_err))
                return {"allowed": False, "error": f"Unable to verify {limit_type} limit"}

        try:
            from app.services.variant_limit_service import (
                get_variant_limit_service,
            )

            service = get_variant_limit_service()
            result = await service.check_ticket_limit(UUID(company_id))
            return result
        except Exception as exc:
            logger.error(
                "variant_check_failed company_id=%s limit_type=%s error=%s",
                company_id,
                limit_type,
                str(exc)[:200],
            )
            return {"allowed": False, "error": "Unable to verify resource limit. Please try again."}
