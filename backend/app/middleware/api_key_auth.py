"""
PARWA API Key Authentication Middleware (F-019)

Authenticates requests using API keys from DB.
Supports both parwa_live_ and parwa_test_ prefixes.
Uses DB-backed validation via api_key_service.
Backward compatible with old in-memory key_store.
"""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.app.middleware.error_handler import build_error_response

# Paths that skip API key auth (public endpoints)
SKIP_PATHS = {"/health", "/ready", "/metrics"}
SKIP_PREFIXES = ("/api/public/", "/api/auth/")


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
        if not raw_key.startswith("parwa_live_") and \
                not raw_key.startswith("parwa_test_"):
            response = await call_next(request)
            return response

        # Try DB-backed validation first
        key_data = None
        if self._has_db_available():
            key_data = await self._validate_db(
                request, raw_key
            )

        # Fallback to in-memory key_store
        if not key_data:
            key_data = self._lookup_key_memory(raw_key)

        if not key_data:
            return self._unauthorized_response(
                request, "Invalid or expired API key"
            )

        if key_data.get("status") != "active":
            return self._unauthorized_response(
                request, "API key has been revoked"
            )

        expires_at = key_data.get("expires_at")
        if expires_at is not None:
            if isinstance(expires_at, str):
                try:
                    from datetime import datetime
                    exp = datetime.fromisoformat(
                        expires_at
                    )
                    expires_at = exp.timestamp()
                except (ValueError, TypeError):
                    pass
            if isinstance(expires_at, (int, float)):
                if time.time() > expires_at:
                    return self._unauthorized_response(
                        request, "API key has expired"
                    )

        # BC-001: Verify company_id
        req_cid = getattr(request.state, "company_id", None)
        key_cid = key_data.get("company_id")
        if req_cid is None and key_cid:
            request.state.company_id = key_cid
            req_cid = key_cid
        if (
            req_cid
            and key_cid
            and req_cid != key_cid
        ):
            return self._forbidden_response(
                request, "API key does not match tenant"
            )

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
        auth_header = request.headers.get(
            "Authorization", ""
        )
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
        self, request: Request, raw_key: str,
    ):
        """Validate key against database."""
        try:
            from database.base import SessionLocal
            from backend.app.services import api_key_service

            db = SessionLocal()
            try:
                record = api_key_service.validate_key(
                    db, raw_key,
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
                        json.JSONDecodeError, TypeError,
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
                    "status": (
                        "active"
                        if not record.revoked
                        else "revoked"
                    ),
                    "expires_at": (
                        record.expires_at.isoformat()
                        if record.expires_at
                        else None
                    ),
                }
            finally:
                db.close()
        except Exception as _exc:
            from backend.app.logger import get_logger
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
        computed = hashlib.sha256(
            raw_key.encode("utf-8")
        ).hexdigest()
        from shared.utils.security import (
            constant_time_compare,
        )
        for stored_hash, key_data in self._key_store.items():
            if constant_time_compare(
                computed, stored_hash
            ):
                return key_data
        return None

    def _unauthorized_response(
        self, request: Request, message: str,
    ) -> JSONResponse:
        cid = getattr(
            request.state, "correlation_id", None
        )
        return build_error_response(
            status_code=401,
            error_code="AUTHENTICATION_ERROR",
            message=message,
            correlation_id=cid,
        )

    def _forbidden_response(
        self, request: Request, message: str,
    ) -> JSONResponse:
        cid = getattr(
            request.state, "correlation_id", None
        )
        return build_error_response(
            status_code=403,
            error_code="AUTHORIZATION_ERROR",
            message=message,
            correlation_id=cid,
        )


def require_scope(required_scope: str):
    """Dependency that checks if the request has
    the required scope (BC-011)."""
    def checker(request: Request):
        api_key = getattr(request.state, "api_key", None)
        if not api_key:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=401,
                detail="API key required",
            )
        scopes = api_key.get("scopes", [])
        from security.api_keys import validate_scopes
        if not validate_scopes(scopes, required_scope):
            from fastapi import HTTPException
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Insufficient scope. "
                    f"Required: {required_scope}"
                ),
            )
    return checker
