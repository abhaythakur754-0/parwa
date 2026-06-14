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

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.tenant_context import (
    clear_tenant_context,
    set_tenant_context,
)

# BC-001: Max allowed length for company_id
MAX_COMPANY_ID_LENGTH = 128


# Import JWT verification lazily to avoid circular imports.
def _extract_company_id_from_jwt(request: Request) -> str | None:
    """Extract company_id from JWT Authorization header.

    This is a fallback for when the APIKeyAuthMiddleware has not
    already set request.state.company_id (i.e., JWT auth path).

    Security (BC-011): Only reads the JWT; does NOT validate
    revocation — that is the route-level dependency's job.
    The middleware only needs company_id for tenant scoping.

    Returns:
        company_id string or None if not found/invalid.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:]
    # Skip API-key tokens — those are handled by APIKeyAuthMiddleware
    if token.startswith("parwa_live_") or token.startswith("parwa_test_"):
        return None

    try:
        from app.core.auth import verify_access_token
        payload = verify_access_token(token)
        return payload.get("company_id")
    except Exception:
        return None


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
    # SECURITY: /api/billing/ and /api/admin/ are NOT excluded here.
    # They require explicit tenant isolation via route-level dependencies.
    PUBLIC_PREFIXES = (
        "/api/auth/",
        "/api/public/",
        "/public/",
        "/api/api-keys",
        "/api/mfa/",
        "/api/client/",
        "/api/webhooks/",
        "/api/jarvis/",
        "/api/jarvis",
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

        # Extract company_id from request state.
        # APIKeyAuthMiddleware may have already set this.
        # If not, fall back to JWT extraction (BC-011).
        # Do NOT accept client-controlled headers (L06).
        company_id = getattr(
            request.state, "company_id", None,
        )

        # Fallback: extract from JWT if API key middleware
        # didn't set it (JWT auth path).
        if not company_id:
            company_id = _extract_company_id_from_jwt(request)

        # Reject empty or whitespace-only company_id (BC-001)
        if not company_id or not company_id.strip():
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
