"""
PARWA — Shared HTTP Utilities

Common helpers used across all route modules.
Avoids duplicating _err(), _hash_password, etc. in each router file.
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict

from fastapi import HTTPException


def _err(msg: str, status: int = 400) -> HTTPException:
    """Create an HTTPException with a detail message."""
    return HTTPException(status_code=status, detail=msg)


def _hash_password(password: str) -> str:
    """Hash a password using SHA-256.

    Phase 9 uses lightweight hash; production should use bcrypt via passlib.
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its stored hash."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest() == password_hash


def _tid(body: Any) -> str:
    """Extract tenant_id from a request body, defaulting to 'default_tenant'."""
    return getattr(body, "tenant_id", None) or "default_tenant"


def _success(msg: str = "OK", **extra: Any) -> Dict[str, Any]:
    """Build a standard success response dict."""
    return {"status": "success", "message": msg, **extra}
