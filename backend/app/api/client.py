"""
PARWA Client API Router (F06)

Endpoints for company profile, settings, password change,
and team management.

All endpoints require JWT auth (BC-011).
All responses use structured JSON (BC-012).
All queries filtered by company_id (BC-001).
"""

import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import (
    get_current_company,
    get_current_user,
    require_roles,
)
from backend.app.exceptions import NotFoundError
from backend.app.schemas.admin import (
    CompanyProfileUpdate,
    CompanySettingsUpdate,
    MessageResponse,
    PasswordChangeRequest,
    TeamMemberUpdate,
)
from backend.app.services import company_service
from backend.app.services.audit_service import log_audit
from database.base import get_db
from database.models.core import User, Company

router = APIRouter(prefix="/api/client", tags=["client"])


def _serialize_settings(settings) -> dict:
    """Convert CompanySetting ORM object to response dict."""
    import json  # noqa: F811

    def _parse_json(val, default):
        if val is None:
            return default
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return default

    return {
        "id": settings.id,
        "company_id": settings.company_id,
        "ooo_status": settings.ooo_status or "inactive",
        "ooo_message": settings.ooo_message,
        "ooo_until": (
            settings.ooo_until.isoformat()
            if settings.ooo_until else None
        ),
        "brand_voice": settings.brand_voice,
        "tone_guidelines": settings.tone_guidelines,
        "prohibited_phrases": _parse_json(
            settings.prohibited_phrases, [],
        ),
        "pii_patterns": _parse_json(
            settings.pii_patterns, [],
        ),
        "custom_regex": _parse_json(
            settings.custom_regex, [],
        ),
        "top_k": settings.top_k or 5,
        "similarity_threshold": float(
            settings.similarity_threshold or 0.70
        ),
        "rerank_model": settings.rerank_model,
        "confidence_thresholds": _parse_json(
            settings.confidence_thresholds, {},
        ),
        "intent_labels": _parse_json(
            settings.intent_labels, [],
        ),
        "custom_rules": _parse_json(
            settings.custom_rules, [],
        ),
        "assignment_rules": _parse_json(
            settings.assignment_rules, [],
        ),
        "created_at": (
            settings.created_at.isoformat()
            if settings.created_at else None
        ),
        "updated_at": (
            settings.updated_at.isoformat()
            if settings.updated_at else None
        ),
    }


def _serialize_company(company) -> dict:
    """Convert Company ORM object to response dict."""
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
    }


def _serialize_user(user: User) -> dict:
    """Convert User ORM object to TeamMemberResponse dict."""
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "phone": user.phone,
        "avatar_url": user.avatar_url,
        "role": user.role,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "mfa_enabled": user.mfa_enabled,
        "created_at": (
            user.created_at.isoformat()
            if user.created_at else None
        ),
    }


# ── Profile Endpoints ──────────────────────────────────────────────


@router.get("/profile")
def get_profile(
    company: Company = Depends(get_current_company),
) -> dict:
    """Get company profile.

    BC-001: Scoped to authenticated user's company.
    """
    return _serialize_company(company)


@router.put("/profile")
def update_profile(
    body: CompanyProfileUpdate,
    user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
) -> dict:
    """Update company profile.

    Only updates provided fields. Audit logs the change.
    """
    data = body.model_dump(exclude_none=True)
    if not data:
        return _serialize_company(company)

    updated = company_service.update_company_profile(
        company_id=company.id,
        data=data,
        db=db,
    )

    log_audit(
        company_id=company.id,
        actor_id=user.id,
        actor_type="user",
        action="update",
        resource_type="company",
        resource_id=company.id,
        new_value=str(data),
    )

    return _serialize_company(updated)


# ── Settings Endpoints ─────────────────────────────────────────────


@router.get("/settings")
def get_settings(
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
) -> dict:
    """Get company settings.

    Auto-creates with defaults if not found.
    """
    settings = company_service.get_company_settings(
        company_id=company.id,
        db=db,
    )
    return _serialize_settings(settings)


@router.put("/settings")
def update_settings(
    body: CompanySettingsUpdate,
    user: User = Depends(get_current_user),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
) -> dict:
    """Update company settings.

    Lists stored as JSON strings in DB, parsed/serialized
    correctly. Audit logs the change.
    """
    data = body.model_dump(exclude_none=True)
    if not data:
        settings = company_service.get_company_settings(
            company_id=company.id,
            db=db,
        )
        return _serialize_settings(settings)

    updated = company_service.update_company_settings(
        company_id=company.id,
        data=data,
        db=db,
    )

    log_audit(
        company_id=company.id,
        actor_id=user.id,
        actor_type="user",
        action="settings_change",
        resource_type="company_settings",
        resource_id=updated.id,
        new_value=str(list(data.keys())),
    )

    return _serialize_settings(updated)


# ── Password Change ────────────────────────────────────────────────


@router.put("/password")
def change_password(
    body: PasswordChangeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Change user password.

    BC-011: Verifies current bcrypt hash, hashes new with
    bcrypt cost 12.
    """
    company_service.change_password(
        user=user,
        current_password=body.current_password,
        new_password=body.new_password,
        db=db,
    )

    log_audit(
        company_id=user.company_id,
        actor_id=user.id,
        actor_type="user",
        action="update",
        resource_type="user",
        resource_id=user.id,
        new_value="password_changed",
    )

    return MessageResponse(message="Password changed successfully")


# ── Team Management ────────────────────────────────────────────────


@router.get("/team")
def get_team(
    user: User = Depends(
        require_roles("owner", "admin"),
    ),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
) -> dict:
    """List team members (paginated).

    Only owners and admins can list team members.
    BC-001: Filtered by company_id.
    """
    users, total = company_service.get_team_members(
        company_id=company.id,
        db=db,
        page=page,
        per_page=per_page,
    )

    total_pages = math.ceil(total / per_page) if total > 0 else 0

    return {
        "items": [_serialize_user(u) for u in users],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
    }


@router.put("/team/{user_id}")
def update_team_member(
    user_id: str,
    body: TeamMemberUpdate,
    user: User = Depends(
        require_roles("owner", "admin"),
    ),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
) -> dict:
    """Update a team member's role or active status.

    Only owner/admin can change roles. Cannot change own role
    to lower. Company must have at least 1 owner.
    """
    data = body.model_dump(exclude_none=True)
    if not data:
        target = db.query(User).filter(
            User.id == user_id,
            User.company_id == company.id,
        ).first()
        if not target:
            raise NotFoundError(
                message="Team member not found",
                details={"user_id": user_id},
            )
        return _serialize_user(target)

    updated = company_service.update_team_member(
        company_id=company.id,
        user_id=user_id,
        data=data,
        actor=user,
        db=db,
    )

    log_audit(
        company_id=company.id,
        actor_id=user.id,
        actor_type="user",
        action="permission_change",
        resource_type="user",
        resource_id=user_id,
        new_value=str(data),
    )

    return _serialize_user(updated)


@router.delete("/team/{user_id}")
def remove_team_member(
    user_id: str,
    user: User = Depends(
        require_roles("owner", "admin"),
    ),
    company: Company = Depends(get_current_company),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Remove a team member (soft delete).

    Sets is_active=False. Cannot remove last owner.
    """
    company_service.remove_team_member(
        company_id=company.id,
        user_id=user_id,
        actor=user,
        db=db,
    )

    log_audit(
        company_id=company.id,
        actor_id=user.id,
        actor_type="user",
        action="delete",
        resource_type="user",
        resource_id=user_id,
    )

    return MessageResponse(
        message="Team member removed successfully"
    )
