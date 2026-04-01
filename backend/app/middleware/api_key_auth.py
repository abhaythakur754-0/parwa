"""
PARWA API Key Authentication Middleware (BC-011)

Authenticates requests using API keys passed in the Authorization header.
Validates scopes and enforces company_id isolation (BC-001).

Header format: Authorization: Bearer pk_xxxxx
BC-011: API keys are hashed in DB, constant-time comparison.
"""

import hashlib
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.app.middleware.error_handler import build_error_response
from security.api_keys import validate_scopes
from shared.utils.security import constant_time_compare

# Header format
API_KEY_HEADER = "Authorization"
API_KEY_PREFIX = "Bearer "

# Paths that skip API key auth (public endpoints)
SKIP_PATHS = {"/health", "/ready", "/metrics"}
SKIP_PREFIXES = ("/api/public/", "/api/auth/")


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Middleware that authenticates requests via API key.

    - Extracts API key from Authorization: Bearer header
    - Validates key against stored hash (constant-time, BC-011)
    - Enforces scope-based access control
    - Sets request.state.api_key with key metadata
    - Company_id must match between key and request (BC-001)
    - Uses constant-time comparison (no timing attacks)

    Note: In production, this will look up the key hash from the database.
    For now, it validates the format and provides the framework.
    """

    def __init__(self, app, key_store=None):
        """Initialize with optional key store.

        Args:
            app: ASGI application.
            key_store: Dict of {key_hash: api_key_dict} for testing.
                       In production, this will be a DB lookup.
        """
        super().__init__(app)
        self._key_store = key_store or {}

    async def dispatch(self, request: Request, call_next):
        # Skip auth for public paths
        if self._should_skip(request.url.path):
            response = await call_next(request)
            return response

        # Extract API key from header
        raw_key = self._extract_key(request)
        if not raw_key:
            response = await call_next(request)
            return response

        # Look up key using constant-time comparison (BC-011)
        key_data = self._lookup_key(raw_key)

        if not key_data:
            # Invalid API key - return 401
            return self._unauthorized_response(
                request, "Invalid or expired API key"
            )

        # Check if key is active
        if key_data.get("status") != "active":
            return self._unauthorized_response(
                request, "API key has been revoked or rotated"
            )

        # Check expiration
        expires_at = key_data.get("expires_at")
        if expires_at is not None:
            if time.time() > expires_at:
                return self._unauthorized_response(
                    request, "API key has expired"
                )

        # BC-001: Verify company_id matches
        request_company_id = getattr(request.state, "company_id", None)
        key_company_id = key_data.get("company_id")

        # If request has no company_id but key does, set it from key
        # This ensures BC-001 tenant isolation is enforced
        if request_company_id is None and key_company_id:
            request.state.company_id = key_company_id
            request_company_id = key_company_id

        if (
            request_company_id
            and key_company_id
            and request_company_id != key_company_id
        ):
            return self._forbidden_response(
                request, "API key does not match tenant"
            )

        # Store key info on request state
        request.state.api_key = {
            "id": key_data.get("id"),
            "scopes": key_data.get("scopes", []),
            "company_id": key_company_id,
            "name": key_data.get("name", ""),
        }

        response = await call_next(request)
        return response

    def _should_skip(self, path: str) -> bool:
        """Check if a path should skip API key authentication."""
        if path in SKIP_PATHS:
            return True
        for prefix in SKIP_PREFIXES:
            if path.startswith(prefix):
                return True
        return False

    def _extract_key(self, request: Request) -> str:
        """Extract API key from Authorization header."""
        auth_header = request.headers.get(API_KEY_HEADER, "")
        if not auth_header.startswith(API_KEY_PREFIX):
            return ""
        return auth_header[len(API_KEY_PREFIX):]

    def _lookup_key(self, raw_key: str):
        """Look up key using constant-time comparison (BC-011).

        Iterates through all stored hashes and compares using
        constant_time_compare to prevent timing attacks.
        Python dict lookup uses str.__eq__ which is NOT constant-time.
        """
        if not raw_key:
            return None
        computed_hash = hashlib.sha256(
            raw_key.encode("utf-8")
        ).hexdigest()

        for stored_hash, key_data in self._key_store.items():
            if constant_time_compare(computed_hash, stored_hash):
                return key_data

        return None

    def _unauthorized_response(
        self, request: Request, message: str
    ) -> JSONResponse:
        """Return 401 Unauthorized response."""
        correlation_id = getattr(
            request.state, "correlation_id", None
        )
        return build_error_response(
            status_code=401,
            error_code="AUTHENTICATION_ERROR",
            message=message,
            correlation_id=correlation_id,
        )

    def _forbidden_response(
        self, request: Request, message: str
    ) -> JSONResponse:
        """Return 403 Forbidden response."""
        correlation_id = getattr(
            request.state, "correlation_id", None
        )
        return build_error_response(
            status_code=403,
            error_code="AUTHORIZATION_ERROR",
            message=message,
            correlation_id=correlation_id,
        )


def require_scope(required_scope: str):
    """Dependency that checks if the request has the required scope.

    BC-011: Scope isolation - read can't write, write can't admin.

    Usage in FastAPI routes:
        @router.get("/admin")
        async def admin_route(request: Request):
            require_scope("admin")(request)
            ...
    """
    def checker(request: Request):
        api_key = getattr(request.state, "api_key", None)
        if not api_key:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=401,
                detail="API key required",
            )

        scopes = api_key.get("scopes", [])
        if not validate_scopes(scopes, required_scope):
            from fastapi import HTTPException
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Insufficient scope. Required: {required_scope}, "
                    f"Granted: {scopes}"
                ),
            )

    return checker
