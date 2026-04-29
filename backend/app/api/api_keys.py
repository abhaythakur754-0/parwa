"""
PARWA API Key Endpoints (F-019)

CRUD endpoints for API key management.
All scoped by company_id from JWT (BC-001).
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.middleware.api_key_auth import require_scope
from app.schemas.api_key import (
    APIKeyCreate,
    APIKeyCreatedResponse,
    APIKeyResponse,
    APIKeyRevokedResponse,
    APIKeyRotatedResponse,
)
from app.services.api_key_service import (
    create_key,
    list_keys,
    revoke_key,
    rotate_key,
)
from database.base import get_db
from database.models.core import User

router = APIRouter(
    prefix="/api/api-keys",
    tags=["API Keys"],
)


@router.get("", response_model=list)
def api_key_list(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _scopes: None = Depends(require_scope("read")),
):
    """List all API keys for the tenant.

    G02: require_scope("read") wired — enforces for API key auth,
    passes through for JWT auth (role-based permissions).
    """
    return list_keys(db, user.company_id)


@router.post("", status_code=201)
def api_key_create(
    body: APIKeyCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    request: Request = None,
    _scopes: None = Depends(require_scope("write")),
):
    """Create a new API key."""
    _ = request  # available for future audit logging
    try:
        raw_key, record = create_key(
            db=db,
            company_id=user.company_id,
            user_id=user.id,
            name=body.name,
            scopes=body.scopes,
            expires_days=body.expires_days,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        if "Maximum" in str(exc):
            from fastapi import HTTPException

            raise HTTPException(
                status_code=400,
                detail=str(exc),
            )
        from fastapi import HTTPException

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        )

    return APIKeyCreatedResponse(
        key=raw_key,
        api_key=_to_response(record),
    )


@router.post("/{key_id}/rotate")
def api_key_rotate(
    key_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _scopes: None = Depends(require_scope("write")),
):
    """Rotate an existing API key."""
    try:
        raw_key, new_rec, old_rec, grace = rotate_key(
            db=db,
            company_id=user.company_id,
            key_id=key_id,
            user_id=user.id,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    return APIKeyRotatedResponse(
        key=raw_key,
        old_key_id=old_rec.id,
        grace_period_ends=grace.isoformat(),
        api_key=_to_response(new_rec),
    )


@router.delete("/{key_id}/revoke")
def api_key_revoke(
    key_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _scopes: None = Depends(require_scope("admin")),
):
    """Revoke an API key immediately."""
    try:
        record = revoke_key(
            db=db,
            company_id=user.company_id,
            key_id=key_id,
            user_id=user.id,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        from fastapi import HTTPException

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    return APIKeyRevokedResponse(
        status="revoked",
        key_id=record.id,
    )


def _to_response(record) -> APIKeyResponse:
    """Convert DB record to APIKeyResponse."""
    import json

    scopes = ["read"]
    if record.scopes:
        try:
            scopes = json.loads(record.scopes)
        except (json.JSONDecodeError, TypeError):
            if record.scope:
                scopes = [record.scope]
    elif record.scope:
        scopes = [record.scope]
    return APIKeyResponse(
        id=record.id,
        name=record.name,
        key_prefix=record.key_prefix,
        scopes=scopes,
        created_at=(record.created_at.isoformat() if record.created_at else None),
        last_used_at=(record.last_used_at.isoformat() if record.last_used_at else None),
        expires_at=(record.expires_at.isoformat() if record.expires_at else None),
        revoked=record.revoked,
    )
