"""
PARWA Admin API Router (F06)

Platform admin endpoints for managing clients (companies),
subscriptions, API providers, and system health.

SECURITY NOTE: Admin endpoints use require_platform_admin() to ensure
only platform administrators can access cross-tenant data. A user must
have is_platform_admin=True on their User record.

All responses use structured JSON (BC-012).
"""

import json
import math
from datetime import datetime as dt, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import (
    require_platform_admin,
)
from app.exceptions import NotFoundError
from app.schemas.admin import (
    AdminClientResponse,
    AdminClientUpdate,
    AdminHealthResponse,
    APIProviderCreate,
    APIProviderListResponse,
    APIProviderResponse,
    APIProviderUpdate,
    ClientListResponse,
    MessageResponse,
    SubscriptionUpdateRequest,
)
from app.services.audit_service import log_audit
from database.base import get_db
from database.models.ai_pipeline import APIProvider
from database.models.core import Company, User

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _serialize_company_with_count(company) -> dict:
    """Serialize company with user count for admin responses."""
    return {
        "id": company.id,
        "name": company.name,
        "industry": company.industry,
        "subscription_tier": company.subscription_tier,
        "subscription_status": company.subscription_status,
        "mode": company.mode,
        "created_at": (
            company.created_at.isoformat()
            if company.created_at else None
        ),
        "updated_at": (
            company.updated_at.isoformat()
            if company.updated_at else None
        ),
        "user_count": getattr(
            company, "_user_count", 0,
        ),
    }


def _serialize_provider(provider) -> dict:
    """Serialize APIProvider ORM object to response dict."""
    def _parse_json(val, default):
        if val is None:
            return default
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return default

    return {
        "id": provider.id,
        "name": provider.name,
        "provider_type": provider.provider_type,
        "description": provider.description,
        "required_fields": _parse_json(
            provider.required_fields, [],
        ),
        "optional_fields": _parse_json(
            provider.optional_fields, [],
        ),
        "default_endpoint": provider.default_endpoint,
        "is_active": provider.is_active,
        "created_at": (
            provider.created_at.isoformat()
            if provider.created_at else None
        ),
    }


# ── Client Management ──────────────────────────────────────────────


@router.get("/clients", response_model=ClientListResponse)
def list_clients(
    user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
) -> dict:
    """List all companies (paginated).

    Platform admin endpoint. Can filter by name search.
    """
    query = db.query(Company)

    if search:
        # M-33 fix: escape ILIKE wildcards to prevent SQL injection
        escaped_search = search.replace("%", r"\\%").replace("_", r"\\_")
        query = query.filter(
            Company.name.ilike(f"%{escaped_search}%", escape="\\"),
        )

    total = query.count()
    per_page = min(per_page, 100)
    offset = (page - 1) * per_page

    companies = query.order_by(
        Company.created_at.desc(),
    ).offset(offset).limit(per_page).all()

    # Annotate with user counts
    items = []
    for c in companies:
        from sqlalchemy import func as sa_func
        count = db.query(sa_func.count(User.id)).filter(
            User.company_id == c.id,
        ).scalar() or 0
        c._user_count = count  # type: ignore[attr-defined]
        items.append(_serialize_company_with_count(c))

    total_pages = (
        math.ceil(total / per_page) if total > 0 else 0
    )

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
    }


@router.get("/clients/{company_id}", response_model=AdminClientResponse)
def get_client_detail(
    company_id: str,
    user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Get single client detail."""
    company = db.query(Company).filter(
        Company.id == company_id,
    ).first()

    if not company:
        raise NotFoundError(
            message="Client not found",
            details={"company_id": company_id},
        )

    from sqlalchemy import func as sa_func
    count = db.query(sa_func.count(User.id)).filter(
        User.company_id == company.id,
    ).scalar() or 0
    company._user_count = count  # type: ignore[attr-defined]

    return _serialize_company_with_count(company)


@router.put("/clients/{company_id}", response_model=AdminClientResponse)
def update_client(
    company_id: str,
    body: AdminClientUpdate,
    user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Update client details."""
    company = db.query(Company).filter(
        Company.id == company_id,
    ).first()

    if not company:
        raise NotFoundError(
            message="Client not found",
            details={"company_id": company_id},
        )

    _UPDATABLE_COMPANY_FIELDS = {"name", "industry", "mode"}
    data = body.model_dump(exclude_none=True)
    for field, value in data.items():
        if field in _UPDATABLE_COMPANY_FIELDS:
            setattr(company, field, value)

    company.updated_at = dt.now(timezone.utc)
    db.commit()
    db.refresh(company)

    from sqlalchemy import func as sa_func
    count = db.query(sa_func.count(User.id)).filter(
        User.company_id == company.id,
    ).scalar() or 0
    company._user_count = count  # type: ignore[attr-defined]

    log_audit(
        company_id=company.id,
        actor_id=user.id,
        actor_type="user",
        action="update",
        resource_type="company",
        resource_id=company_id,
        new_value=str(data),
        db=db,
    )

    return _serialize_company_with_count(company)


@router.put("/clients/{company_id}/subscription", response_model=AdminClientResponse)
def update_subscription(
    company_id: str,
    body: SubscriptionUpdateRequest,
    user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Change subscription tier/status."""
    company = db.query(Company).filter(
        Company.id == company_id,
    ).first()

    if not company:
        raise NotFoundError(
            message="Client not found",
            details={"company_id": company_id},
        )

    if body.tier is not None:
        company.subscription_tier = body.tier.value
    if body.status is not None:
        company.subscription_status = body.status.value

    company.updated_at = dt.now(timezone.utc)
    db.commit()
    db.refresh(company)

    from sqlalchemy import func as sa_func
    count = db.query(sa_func.count(User.id)).filter(
        User.company_id == company.id,
    ).scalar() or 0
    company._user_count = count  # type: ignore[attr-defined]

    log_audit(
        company_id=company.id,
        actor_id=user.id,
        actor_type="user",
        action="update",
        resource_type="subscription",
        resource_id=company_id,
        new_value=body.model_dump_json(),
        db=db,
    )

    return _serialize_company_with_count(company)


# ── Health ──────────────────────────────────────────────────────────


@router.get("/health", response_model=AdminHealthResponse)
def admin_health(
    # C-10 FIX: Require platform admin auth on admin health endpoint
    user: User = Depends(require_platform_admin),
) -> dict:
    """System health summary for admin panel.

    C-10 FIX: Now requires platform admin authentication.
    Previously had no auth check, allowing anyone to probe admin endpoints.
    """
    return {
        "status": "ok",
        "message": "System operational",
    }


# ── API Provider Management ────────────────────────────────────────


@router.get("/api-providers", response_model=APIProviderListResponse)
def list_api_providers(
    user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """List all API providers (global)."""
    providers = db.query(APIProvider).filter(
        APIProvider.is_active == True,  # noqa: E712
    ).order_by(APIProvider.name).all()
    return {
        "items": [_serialize_provider(p) for p in providers],
    }


@router.post("/api-providers", response_model=APIProviderResponse)
def create_api_provider(
    body: APIProviderCreate,
    user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Create a new API provider."""
    data = body.model_dump(exclude_none=True)

    provider = APIProvider(
        name=data["name"],
        provider_type=data["provider_type"],
        description=data.get("description"),
        required_fields=json.dumps(
            data.get("required_fields", []),
        ),
        optional_fields=json.dumps(
            data.get("optional_fields", []),
        ),
        default_endpoint=data.get("default_endpoint"),
        is_active=True,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)

    log_audit(
        company_id=user.company_id,
        actor_id=user.id,
        actor_type="user",
        action="create",
        resource_type="api_provider",
        resource_id=provider.id,
        new_value=provider.name,
        db=db,
    )

    return _serialize_provider(provider)


@router.put("/api-providers/{provider_id}", response_model=APIProviderResponse)
def update_api_provider(
    provider_id: str,
    body: APIProviderUpdate,
    user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Update an API provider."""
    provider = db.query(APIProvider).filter(
        APIProvider.id == provider_id,
    ).first()

    if not provider:
        raise NotFoundError(
            message="API provider not found",
            details={"provider_id": provider_id},
        )

    data = body.model_dump(exclude_none=True)

    _UPDATABLE_PROVIDER_FIELDS = {"name", "description", "provider_type", "default_endpoint", "required_fields", "optional_fields"}
    for field, value in data.items():
        if field in _UPDATABLE_PROVIDER_FIELDS:
            if field in ("required_fields", "optional_fields") and isinstance(value, list):
                value = json.dumps(value)
            setattr(provider, field, value)

    db.commit()
    db.refresh(provider)

    log_audit(
        company_id=user.company_id,
        actor_id=user.id,
        actor_type="user",
        action="update",
        resource_type="api_provider",
        resource_id=provider_id,
        new_value=body.model_dump_json(),
        db=db,
    )

    return _serialize_provider(provider)


@router.delete("/api-providers/{provider_id}", response_model=MessageResponse)
def delete_api_provider(
    provider_id: str,
    user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Soft-delete an API provider (set is_active=False)."""
    provider = db.query(APIProvider).filter(
        APIProvider.id == provider_id,
    ).first()

    if not provider:
        raise NotFoundError(
            message="API provider not found",
            details={"provider_id": provider_id},
        )

    provider.is_active = False
    db.commit()

    log_audit(
        company_id=user.company_id,
        actor_id=user.id,
        actor_type="user",
        action="delete",
        resource_type="api_provider",
        resource_id=provider_id,
        db=db,
    )

    return MessageResponse(
        message="API provider deactivated successfully"
    )
