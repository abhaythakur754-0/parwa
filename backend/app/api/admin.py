"""
PARWA Admin API Router (F06)

Platform admin endpoints for managing clients (companies),
subscriptions, API providers, and system health.

SECURITY NOTE (A7): All admin endpoints now require platform admin
access via ``require_platform_admin`` dependency. This checks
``PLATFORM_ADMIN_EMAILS`` env var first, then falls back to
``role="owner"`` for backward compatibility.

TENANT ISOLATION NOTE: Admin endpoints are INTENTIONALLY cross-tenant.
The ``require_platform_admin`` guard is the sole access control.
Path parameters (company_id) are validated for UUID format.
Global resources (API providers, webhook retry) use "platform" as
the audit company_id since they are not tenant-scoped.

TODO (Alembic Migration): Add an ``is_platform_admin`` boolean column
to the User model. Once the migration is created and applied, the
guard should check ``user.is_platform_admin`` directly instead of
relying on the env-var email allowlist or role fallback.
See: ``alembic revision --autogenerate -m "add is_platform_admin to user"``

All responses use structured JSON (BC-012).
"""

import json
import math
import os
import re
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
)
from app.exceptions import AuthorizationError, NotFoundError
from app.schemas.admin import (
    AdminClientUpdate,
    APIProviderCreate,
    APIProviderUpdate,
    MessageResponse,
    SubscriptionUpdateRequest,
)
from app.services.audit_service import log_audit
from database.base import get_db
from database.models.ai_pipeline import APIProvider
from database.models.core import Company, User

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Sentinel for audit logs on global (non-tenant) resources
_PLATFORM_AUDIT_COMPANY_ID = "platform"

# UUID format pattern for path validation
_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _validate_uuid(value: str, param_name: str = "id") -> None:
    """Validate that a path parameter is a valid UUID.

    Raises NotFoundError for invalid format to avoid leaking
    information about whether a resource exists.
    """
    if not value or not _UUID_PATTERN.match(value):
        raise NotFoundError(
            message=f"Invalid {param_name} format",
            details={param_name: value},
        )


# A7: Platform admin email allowlist.
# NOTE: This requires an Alembic migration to add `is_platform_admin`
#       boolean column to the User model. Once available, prefer
#       checking `user.is_platform_admin` over the env-var approach.
#       Migration command:
#         alembic revision --autogenerate -m "add is_platform_admin to user"
def require_platform_admin(
    user: User = Depends(get_current_user),
) -> User:
    """Verify the authenticated user is a platform admin.

    A7: Checks the user's email against PLATFORM_ADMIN_EMAILS.
    Falls back to role="owner" check when the env var is not set,
    preserving backward compatibility.
    """
    admin_emails_raw = os.environ.get("PLATFORM_ADMIN_EMAILS", "")
    if admin_emails_raw:
        admin_emails = {
            e.strip().lower()
            for e in admin_emails_raw.split(",")
            if e.strip()
        }
        if user.email and user.email.lower() in admin_emails:
            return user
        raise AuthorizationError(
            message="Platform admin access required",
            details={"user_email": user.email},
        )
    # Fallback: when PLATFORM_ADMIN_EMAILS is not configured,
    # require the owner role (existing behaviour).
    if user.role == "owner":
        return user
    raise AuthorizationError(
        message="Platform admin access required",
        details={"user_role": user.role},
    )


def _serialize_company_with_count(company) -> dict:
    """Serialize company with user count for admin responses."""
    return {
        "id": company.id,
        "name": company.name,
        "industry": company.industry,
        "subscription_tier": company.subscription_tier,
        "subscription_status": company.subscription_status,
        "mode": company.mode,
        "paddle_customer_id": company.paddle_customer_id,
        "paddle_subscription_id": (
            company.paddle_subscription_id
        ),
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


@router.get("/clients")
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
        # B3: Escape LIKE wildcards to prevent injection
        safe_search = search.replace("%", r"\%").replace("_", r"\_")
        query = query.filter(
            Company.name.ilike(f"%{safe_search}%", escape="\\"),
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


@router.get("/clients/{company_id}")
def get_client_detail(
    company_id: str,
    user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Get single client detail."""
    _validate_uuid(company_id, "company_id")
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


@router.put("/clients/{company_id}")
def update_client(
    company_id: str,
    body: AdminClientUpdate,
    user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Update client details."""
    _validate_uuid(company_id, "company_id")
    company = db.query(Company).filter(
        Company.id == company_id,
    ).first()

    if not company:
        raise NotFoundError(
            message="Client not found",
            details={"company_id": company_id},
        )

    data = body.model_dump(exclude_none=True)
    for field, value in data.items():
        if hasattr(company, field):
            setattr(company, field, value)

    from datetime import datetime as dt
    company.updated_at = dt.utcnow()
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


@router.put("/clients/{company_id}/subscription")
def update_subscription(
    company_id: str,
    body: SubscriptionUpdateRequest,
    user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Change subscription tier/status."""
    _validate_uuid(company_id, "company_id")
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

    from datetime import datetime as dt
    company.updated_at = dt.utcnow()
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


@router.get("/health")
def admin_health() -> dict:
    """System health summary for admin panel."""
    return {
        "status": "ok",
        "message": "System operational",
    }


# ── API Provider Management ────────────────────────────────────────


@router.get("/api-providers")
def list_api_providers(
    user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """List all API providers (global)."""
    providers = db.query(APIProvider).filter(
        APIProvider.is_active is True,  # noqa: E712
    ).order_by(APIProvider.name).all()
    return {
        "items": [_serialize_provider(p) for p in providers],
    }


@router.post("/api-providers")
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
        company_id=_PLATFORM_AUDIT_COMPANY_ID,
        actor_id=user.id,
        actor_type="user",
        action="create",
        resource_type="api_provider",
        resource_id=provider.id,
        new_value=provider.name,
        db=db,
    )

    return _serialize_provider(provider)


@router.put("/api-providers/{provider_id}")
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

    for field, value in data.items():
        if field in ("required_fields", "optional_fields"):
            if isinstance(value, list):
                value = json.dumps(value)
        if hasattr(provider, field):
            setattr(provider, field, value)

    db.commit()
    db.refresh(provider)

    log_audit(
        company_id=_PLATFORM_AUDIT_COMPANY_ID,
        actor_id=user.id,
        actor_type="user",
        action="update",
        resource_type="api_provider",
        resource_id=provider_id,
        new_value=body.model_dump_json(),
        db=db,
    )

    return _serialize_provider(provider)


@router.delete("/api-providers/{provider_id}")
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
        company_id=_PLATFORM_AUDIT_COMPANY_ID,
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


# ── Webhook Management ────────────────────────────────────────────


@router.post("/webhooks/{webhook_id}/retry")
def retry_failed_webhook_endpoint(
    webhook_id: str,
    user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Retry a failed webhook event. Admin only.

    Resets the event to pending status, clears error info,
    increments the attempt counter, and re-dispatches to Celery
    for asynchronous processing.

    BC-011: Admin-only access.
    BC-012: Structured JSON response.
    """
    if not webhook_id or not webhook_id.strip():
        raise NotFoundError(
            message="webhook_id is required",
            details={"webhook_id": webhook_id},
        )

    try:
        from app.services.webhook_service import retry_failed_webhook

        result = retry_failed_webhook(webhook_id)

        log_audit(
            company_id=_PLATFORM_AUDIT_COMPANY_ID,
            actor_id=user.id,
            actor_type="user",
            action="retry",
            resource_type="webhook_event",
            resource_id=webhook_id,
            new_value=str(result.get("status")),
            db=db,
        )

        return result

    except ValueError as ve:
        raise NotFoundError(
            message=str(ve),
            details={"webhook_id": webhook_id},
        )
    except Exception as exc:
        log_audit(
            company_id=_PLATFORM_AUDIT_COMPANY_ID,
            actor_id=user.id,
            actor_type="user",
            action="retry_failed",
            resource_type="webhook_event",
            resource_id=webhook_id,
            new_value=f"error: {str(exc)[:200]}",
            db=db,
        )
        raise
