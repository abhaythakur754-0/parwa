"""
PARWA Tenant Middleware (BC-001)

Extracts company_id from JWT token and ensures multi-tenant isolation.
- Every authenticated request MUST have a company_id
- Missing company_id -> 403 Forbidden
- Tenant isolation is enforced at the database level via company_id index
- Auth endpoints are excluded (handled by route-level deps)

Day 20: Added tenant context propagation via set_tenant_context()/clear_tenant_context()
so all downstream code (DB auto-injection, Redis key scoping, Celery task headers)
can access the current tenant without explicit parameter passing.
"""

import logging

from app.core.tenant_context import (
    clear_tenant_context,
    set_tenant_context,
)
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("parwa.tenant_middleware")

# BC-001: Max allowed length for company_id
MAX_COMPANY_ID_LENGTH = 128


class TenantMiddleware(BaseHTTPMiddleware):
    """Middleware that extracts and validates company_id from JWT."""

    # Paths that skip tenant check entirely
    PUBLIC_PATHS = {
        "/health",
        "/ready",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
    }

    # Prefixes that skip tenant check (auth handles its own
    # via route-level get_current_user dependency)
    # B1: Reduced to only truly public paths.
    # Removed /api/billing/, /api/api-keys, /api/mfa/, /api/client/
    # which now require authentication (tenant middleware enforces company_id).
    PUBLIC_PREFIXES = (
        "/api/auth/",
        "/api/public/",
        "/public/",
        "/api/admin/",
        "/api/webhooks/",
        "/api/jarvis/",
        "/api/jarvis",
        "/api/pricing/",
        "/test/",
    )

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # Skip tenant check for public/health/auth endpoints
        if path in self.PUBLIC_PATHS:
            return await call_next(request)
        for prefix in self.PUBLIC_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # DEBUG: Log the path if we are about to block it
        # logger.debug(f"TenantMiddleware check: path={path}")

        # Extract company_id from request state only.
        # JWT verification happens in get_current_user dependency.
        # Do NOT accept client-controlled headers (L06).
        company_id = getattr(
            request.state,
            "company_id",
            None,
        )

        # Reject empty or whitespace-only company_id (BC-001)
        if not company_id or not company_id.strip():
            logger.warning("tenant_blocked_no_company_id path=%s", path)
            return Response(
                content=(
                    '{"error":{"code":"AUTHORIZATION_ERROR",'
                    '"message":"Tenant identification required",'
                    '"details":null}}'
                ),
                status_code=403,
                media_type="application/json",
            )

        # Store in request state for downstream use (stripped)
        company_id = company_id.strip()

        # BC-001: Validate company_id length and format
        if len(company_id) > MAX_COMPANY_ID_LENGTH:
            logger.warning(
                "tenant_blocked_id_too_long path=%s company_id_len=%d",
                path,
                len(company_id),
            )
            return Response(
                content=(
                    '{"error":{"code":"BAD_REQUEST",'
                    '"message":"Tenant ID too long",'
                    '"details":null}}'
                ),
                status_code=400,
                media_type="application/json",
            )

        # Reject company_id with control characters or null bytes
        if any(ord(c) < 32 for c in company_id):
            logger.warning("tenant_blocked_invalid_format path=%s", path)
            return Response(
                content=(
                    '{"error":{"code":"BAD_REQUEST",'
                    '"message":"Invalid tenant ID format",'
                    '"details":null}}'
                ),
                status_code=400,
                media_type="application/json",
            )

        request.state.company_id = company_id

        # Day 20: Propagate tenant context for downstream consumers
        # (DB auto-injection, Redis key validation, Celery task headers)
        set_tenant_context(company_id)

        try:
            response = await call_next(request)
        finally:
            # Day 20: Always clear context to prevent leaking between requests
            clear_tenant_context()

        return response
