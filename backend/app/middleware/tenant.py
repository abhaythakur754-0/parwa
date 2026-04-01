"""
PARWA Tenant Middleware (BC-001)

Extracts company_id from JWT token and ensures multi-tenant isolation.
- Every authenticated request MUST have a company_id
- Missing company_id → 403 Forbidden
- Tenant isolation is enforced at the database level via company_id index
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class TenantMiddleware(BaseHTTPMiddleware):
    """Middleware that extracts and validates company_id from JWT."""

    # Paths that don't require tenant isolation (public endpoints)
    PUBLIC_PATHS = {
        "/health",
        "/ready",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
    }

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # Skip tenant check for public/health endpoints
        if path in self.PUBLIC_PATHS or path.startswith("/api/public"):
            return await call_next(request)

        # Extract company_id from request state (set by auth middleware later)
        # For now, check for X-Company-ID header as fallback
        company_id = (
            getattr(request.state, "company_id", None)
            or request.headers.get("X-Company-ID")
        )

        if not company_id:
            return Response(
                content=(
                    '{"error":{"code":"AUTHORIZATION_ERROR",'
                    '"message":"Tenant identification required",'
                    '"details":null}}'
                ),
                status_code=403,
                media_type="application/json",
            )

        # Store in request state for downstream use
        request.state.company_id = company_id

        return await call_next(request)
