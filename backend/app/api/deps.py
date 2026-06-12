"""
PARWA Phase 3 — Dependency Injection for API Routes

Provides FastAPI dependency callables that every route handler uses to
obtain database sessions, tenant context, and service instances.

CRITICAL RULES:
- BC-001: company_id is ALWAYS extracted from the JWT / request header
- BC-008: Every dependency is wrapped in try/except — never crash
- No mock data, no placeholder emails
"""

from __future__ import annotations

import logging
from typing import Generator, Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from database.base import get_db as _get_db_session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Database session
# ---------------------------------------------------------------------------

def get_db() -> Generator[Session, None, None]:
    """Yield a database session with guaranteed cleanup.

    Thin wrapper around the shared ``get_db`` from ``database.base``
    to keep the import path consistent for ``Depends()``.

    NOTE: HTTPException is re-raised without wrapping so route handlers
    can control their own status codes. Only genuine DB errors become 503.
    """
    try:
        yield from _get_db_session()
    except HTTPException:
        raise  # let route handler HTTP exceptions pass through
    except Exception as exc:
        logger.error("get_db dependency failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database session unavailable",
        ) from exc


# ---------------------------------------------------------------------------
# Tenant identity (company_id)
# ---------------------------------------------------------------------------

def get_current_company_id(
    x_company_id: Optional[str] = Header(None, alias="X-Company-Id"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> str:
    """Extract and validate company_id from JWT token or X-Company-Id header.

    Priority:
    1. JWT Authorization header (Bearer token) — extract company_id from claims
    2. X-Company-Id header — backward compatible fallback

    BC-001: Every endpoint MUST receive company_id through this
    dependency — no other source is acceptable.
    """
    try:
        # Try JWT first
        if authorization and authorization.startswith("Bearer "):
            try:
                import jwt as pyjwt
                from app.config import settings

                token = authorization[7:]
                payload = pyjwt.decode(
                    token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
                )
                company_id = payload.get("company_id")
                if company_id:
                    return str(company_id).strip()
            except Exception:
                pass  # fall through to header

        # Fallback to header
        if x_company_id:
            return x_company_id.strip()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication (JWT or X-Company-Id required)",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_current_company_id failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to extract company identity",
        ) from exc


# ---------------------------------------------------------------------------
# Credential encryption service
# ---------------------------------------------------------------------------

def get_credential_service():
    """Return a ``CredentialService`` instance configured with the master key.

    Never raises (BC-008) — returns None on failure.
    """
    try:
        import os
        from app.core.credentials import CredentialService

        master_key = os.getenv(
            "ENCRYPTION_MASTER_KEY",
            "dev-master-key-change-in-production-32ch",
        )
        if len(master_key) < 16:
            master_key = master_key + "x" * (16 - len(master_key))
        return CredentialService(master_key)
    except Exception as exc:
        logger.error("get_credential_service failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# SmartCache
# ---------------------------------------------------------------------------

def get_cache():
    """Return a ``SmartCache`` instance.

    Never raises (BC-008) — returns a new instance on every call so
    that a failed Redis connection degrades gracefully.
    """
    try:
        from app.core.cache import SmartCache

        return SmartCache(redis_url="redis://localhost:6379")
    except Exception as exc:
        logger.error("get_cache failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# AuditTrailService
# ---------------------------------------------------------------------------

def get_audit_trail():
    """Return the shared ``AuditTrailService`` singleton.

    Never raises (BC-008).
    """
    try:
        from app.core.audit_trail import AuditTrailService

        return AuditTrailService()
    except Exception as exc:
        logger.error("get_audit_trail failed: %s", exc)
        return None
