"""
PARWA API Key Authentication Middleware (F-019)

Authenticates requests using API keys from DB.
Supports both parwa_live_ and parwa_test_ prefixes.
Uses DB-backed validation via api_key_service.
Backward compatible with old in-memory key_store.
"""

import time

from app.middleware.error_handler import build_error_response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# Paths that skip API key auth (public endpoints)
SKIP_PATHS = {"/health", "/ready", "/metrics"}
SKIP_PREFIXES = ("/api/public/", "/api/auth/", "/public/")


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Middleware that authenticates requests via API key.

    - Extracts API key from Authorization: Bearer header
    - Supports parwa_live_ and parwa_test_ prefixes
    - DB-backed validation via api_key_service
    - Sets request.state.api_key with key metadata
    - Falls back to in-memory key_store if provided
    - BC-001: company_id from key must match request
    """

    def __init__(self, app, key_store=None):
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
            # No Bearer token at all — pass through
            response = await call_next(request)
            return response

        # Only validate tokens with parwa_ prefix as API keys
        # JWT tokens (dot-separated) should pass through to
        # the route-level auth dependency (get_current_user)
        if not raw_key.startswith("parwa_live_") and not raw_key.startswith(
            "parwa_test_"
        ):
            response = await call_next(request)
            return response

        # Try DB-backed validation first
        key_data = None
        if self._has_db_available():
            key_data = await self._validate_db(request, raw_key)

        # Fallback to in-memory key_store
        if not key_data:
            key_data = self._lookup_key_memory(raw_key)

        if not key_data:
            return self._unauthorized_response(request, "Invalid or expired API key")

        if key_data.get("status") != "active":
            return self._unauthorized_response(request, "API key has been revoked")

        expires_at = key_data.get("expires_at")
        if expires_at is not None:
            if isinstance(expires_at, str):
                try:
                    from datetime import datetime

                    exp = datetime.fromisoformat(expires_at)
                    expires_at = exp.timestamp()
                except (ValueError, TypeError):
                    pass
            if isinstance(expires_at, (int, float)):
                if time.time() > expires_at:
                    return self._unauthorized_response(request, "API key has expired")

        # BC-001: Verify company_id
        req_cid = getattr(request.state, "company_id", None)
        key_cid = key_data.get("company_id")
        if req_cid is None and key_cid:
            request.state.company_id = key_cid
            req_cid = key_cid
        if req_cid and key_cid and req_cid != key_cid:
            return self._forbidden_response(request, "API key does not match tenant")

        request.state.api_key = {
            "id": key_data.get("id"),
            "scopes": key_data.get("scopes", []),
            "company_id": key_cid,
            "name": key_data.get("name", ""),
        }

        response = await call_next(request)
        return response

    def _should_skip(self, path: str) -> bool:
        if path in SKIP_PATHS:
            return True
        for prefix in SKIP_PREFIXES:
            if path.startswith(prefix):
                return True
        return False

    def _extract_key(self, request: Request) -> str:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return ""
        return auth_header[7:]

    def _has_db_available(self) -> bool:
        """Check if DB-backed validation is available."""
        try:
            from database.base import SessionLocal as _  # noqa: F401

            return True
        except Exception:
            return False

    async def _validate_db(
        self,
        request: Request,
        raw_key: str,
    ):
        """Validate key against database."""
        try:
            from app.services import api_key_service

            from database.base import SessionLocal

            db = SessionLocal()
            try:
                record = api_key_service.validate_key(
                    db,
                    raw_key,
                )
                if not record:
                    return None

                # Update last used
                ip = ""
                if request.client:
                    ip = request.client.host
                api_key_service.update_last_used(
                    db,
                    record.id,
                    request.url.path,
                    ip,
                )
                db.commit()

                import json

                scopes = ["read"]
                if record.scopes:
                    try:
                        scopes = json.loads(record.scopes)
                    except (
                        json.JSONDecodeError,
                        TypeError,
                    ):
                        if record.scope:
                            scopes = [record.scope]
                elif record.scope:
                    scopes = [record.scope]

                return {
                    "id": record.id,
                    "name": record.name,
                    "company_id": record.company_id,
                    "scopes": scopes,
                    "status": ("active" if not record.revoked else "revoked"),
                    "expires_at": (
                        record.expires_at.isoformat() if record.expires_at else None
                    ),
                }
            finally:
                db.close()
        except Exception as _exc:
            from app.logger import get_logger

            get_logger("api_key_auth").warning(
                "api_key_db_validation_failed",
                error=str(_exc),
            )
            return None

    def _lookup_key_memory(self, raw_key: str):
        """Fallback: in-memory key lookup."""
        if not raw_key:
            return None
        import hashlib

        computed = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        from shared.utils.security import (
            constant_time_compare,
        )

        for stored_hash, key_data in self._key_store.items():
            if constant_time_compare(computed, stored_hash):
                return key_data
        return None

    def _unauthorized_response(
        self,
        request: Request,
        message: str,
    ) -> JSONResponse:
        cid = getattr(request.state, "correlation_id", None)
        return build_error_response(
            status_code=401,
            error_code="AUTHENTICATION_ERROR",
            message=message,
            correlation_id=cid,
        )

    def _forbidden_response(
        self,
        request: Request,
        message: str,
    ) -> JSONResponse:
        cid = getattr(request.state, "correlation_id", None)
        return build_error_response(
            status_code=403,
            error_code="AUTHORIZATION_ERROR",
            message=message,
            correlation_id=cid,
        )


def require_scope(required_scope: str):
    """Dependency that checks API key scope (BC-011).

    Only enforces scope when request is authenticated via API key.
    Passes through when authenticated via JWT (user on state),
    since JWT users have role-based permissions.
    """

    def checker(request: Request):
        api_key = getattr(request.state, "api_key", None)
        if not api_key:
            # No API key — request uses JWT auth, pass through
            return
        scopes = api_key.get("scopes", [])
        from security.api_keys import validate_scopes

        if not validate_scopes(scopes, required_scope):
            from fastapi import HTTPException

            raise HTTPException(
                status_code=403,
                detail=("Insufficient scope. " f"Required: {required_scope}"),
            )

    return checker


def require_financial_approval(request: Request) -> bool:
    """Check if request has BOTH write AND approval scopes.

    G03: Financial approval dual-scope.
    Returns True only if both "write" and "approval" are
    present in the API key scopes.
    Returns False otherwise.

    Args:
        request: The incoming request.

    Returns:
        True if both scopes present, False otherwise.
    """
    api_key = getattr(request.state, "api_key", None)
    if not api_key:
        return False
    scopes = api_key.get("scopes", [])
    return "write" in scopes and "approval" in scopes


def require_financial_approval_dep(request: Request):
    """FastAPI dependency for G03: financial approval dual-scope.

    Enforces that the request has BOTH 'write' AND 'approval'
    scopes when authenticated via API key. Passes through when
    authenticated via JWT (user on state), since JWT users have
    role-based permissions.

    Usage:
        @router.post(\"/api/billing/approve\")
        async def approve(
            _auth: None = Depends(require_financial_approval_dep),
            user: User = Depends(get_current_user),
        ):
            ...
    """
    from fastapi import HTTPException

    api_key = getattr(request.state, "api_key", None)
    if not api_key:
        # No API key — JWT auth, pass through
        return
    scopes = api_key.get("scopes", [])
    has_write = "write" in scopes
    has_approval = "approval" in scopes
    if not has_write or not has_approval:
        raise HTTPException(
            status_code=403,
            detail=(
                "Insufficient scope. Financial approval "
                "requires both 'write' and 'approval' scopes."
            ),
        )
