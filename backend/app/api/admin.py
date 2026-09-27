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


# ════════════════════════════════════════════════════════════════════
# ROI + SENTIMENT ENDPOINTS (platform-wide aggregations)
# ════════════════════════════════════════════════════════════════════
#
# These endpoints power the dashboard's "AI Cost Savings & ROI" and
# "Sentiment Overview" cards. They aggregate data across ALL companies
# (platform-admin scope) so the founder/operator can see platform-wide
# trends, not just one tenant.
#
# Per CLAUDE.md BC-001: every query is platform-scoped (no company_id
# filter) because the caller is a platform admin. Per BC-008: every
# query is wrapped in try/except and degrades to zero-values instead
# of crashing the dashboard.


@router.get(
    "/roi",
    summary="Platform-wide ROI snapshot for the admin dashboard",
)
def admin_roi(
    user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
) -> dict:
    """Get platform-wide ROI snapshot.

    Aggregates across ALL companies:
      - tickets_ai_resolved: count of tickets closed by AI agents
      - tickets_human_resolved: count of tickets closed by human agents
      - avg_ai_cost / avg_human_cost: USD per ticket
      - total_savings: (human_cost - ai_cost) summed across platform
      - savings_percentage: total_savings / human_cost * 100
      - ai_accuracy_pct: weighted average of AI accuracy
      - automation_rate: ai_resolved / total_resolved * 100

    Falls back to zero-values when no data exists (BC-008).
    """
    from datetime import datetime, timedelta, timezone

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # 1. Pull the most recent ROISnapshot per company in the window.
        # ROISnapshot is a per-company, per-period aggregate stored by the
        # analytics_tasks.calculate_roi Celery task.
        from database.models.analytics import ROISnapshot

        snapshots = (
            db.query(ROISnapshot)
            .filter(ROISnapshot.snapshot_date >= cutoff)
            .all()
        )

        if not snapshots:
            return {
                "tickets_ai_resolved": 0,
                "tickets_human_resolved": 0,
                "avg_ai_cost": 0.0,
                "avg_human_cost": 0.0,
                "total_savings": 0.0,
                "savings_percentage": 0.0,
                "ai_accuracy_pct": 0.0,
                "automation_rate": 0.0,
                "period_days": days,
                "companies_analyzed": 0,
            }

        # 2. Sum the per-company snapshots
        total_ai = sum(s.tickets_ai_resolved or 0 for s in snapshots)
        total_human = sum(s.tickets_human_resolved or 0 for s in snapshots)
        total_tickets = total_ai + total_human

        # 3. Weighted averages (avoid divide-by-zero)
        # avg_ai_cost is weighted by tickets_ai_resolved so a company with
        # 10k tickets influences the average more than one with 10.
        if total_ai > 0:
            avg_ai_cost = sum(
                (s.avg_ai_cost or 0) * (s.tickets_ai_resolved or 0)
                for s in snapshots
            ) / total_ai
        else:
            avg_ai_cost = 0.0

        if total_human > 0:
            avg_human_cost = sum(
                (s.avg_human_cost or 0) * (s.tickets_human_resolved or 0)
                for s in snapshots
            ) / total_human
        else:
            # Industry-standard fallback: $8/ticket human-handling cost
            avg_human_cost = 8.0

        # 4. Total savings + automation rate
        total_savings = sum(s.total_savings or 0 for s in snapshots)
        human_cost_total = avg_human_cost * total_human
        savings_percentage = (
            (total_savings / human_cost_total * 100)
            if human_cost_total > 0
            else 0.0
        )

        # 5. Weighted AI accuracy
        if total_ai > 0:
            ai_accuracy = sum(
                (s.ai_accuracy_pct or 0) * (s.tickets_ai_resolved or 0)
                for s in snapshots
            ) / total_ai
        else:
            ai_accuracy = 0.0

        automation_rate = (
            (total_ai / total_tickets * 100) if total_tickets > 0 else 0.0
        )

        return {
            "tickets_ai_resolved": total_ai,
            "tickets_human_resolved": total_human,
            "avg_ai_cost": round(float(avg_ai_cost), 2),
            "avg_human_cost": round(float(avg_human_cost), 2),
            "total_savings": round(float(total_savings), 2),
            "savings_percentage": round(float(savings_percentage), 2),
            "ai_accuracy_pct": round(float(ai_accuracy), 2),
            "automation_rate": round(float(automation_rate), 2),
            "period_days": days,
            "companies_analyzed": len(snapshots),
        }

    except Exception as exc:
        # BC-008: never crash — return zero-values so the dashboard card
        # renders a clear "—" instead of an error page.
        import logging
        logging.getLogger("parwa.admin").exception(
            "admin_roi_failed: %s", exc
        )
        return {
            "tickets_ai_resolved": 0,
            "tickets_human_resolved": 0,
            "avg_ai_cost": 0.0,
            "avg_human_cost": 0.0,
            "total_savings": 0.0,
            "savings_percentage": 0.0,
            "ai_accuracy_pct": 0.0,
            "automation_rate": 0.0,
            "period_days": days,
            "companies_analyzed": 0,
            "error": "roi_calculation_failed",
        }


@router.get(
    "/sentiment",
    summary="Platform-wide sentiment overview for the admin dashboard",
)
def admin_sentiment(
    user: User = Depends(require_platform_admin),
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
) -> dict:
    """Get platform-wide sentiment overview.

    Aggregates across ALL companies:
      - avg_frustration_score: 0.0-1.0 (higher = more frustrated)
      - emotion_distribution: {emotion_name: count}
      - escalation_count: tickets auto-escalated due to high frustration
      - total_analyzed: total sentiment analyses performed
      - positive_ratio / negative_ratio: fraction of conversations

    Falls back to zero-values when no data exists (BC-008).
    """
    from datetime import datetime, timedelta, timezone
    from collections import defaultdict

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # 1. Try the in-process analytics_service sentiment metrics first.
        # This works without any DB tables — uses the in-memory event buffer.
        from app.services.analytics_service import get_sentiment_metrics

        sentiment_data = get_sentiment_metrics()

        total_analyzed = int(sentiment_data.get("total_analyses", 0))
        if total_analyzed == 0:
            return {
                "avg_frustration_score": 0.0,
                "emotion_distribution": {},
                "escalation_count": 0,
                "total_analyzed": 0,
                "positive_ratio": 0.0,
                "negative_ratio": 0.0,
                "period_days": days,
            }

        # 2. Map the analytics_service output to the dashboard's expected shape
        avg_frustration = float(sentiment_data.get("average_frustration", 0.0))
        emotion_dist = sentiment_data.get("emotion_distribution", {})
        escalation_count = int(sentiment_data.get("escalation_count", 0))

        # 3. Compute positive/negative ratios from the emotion distribution.
        # Map emotion names to sentiment polarity.
        POSITIVE_EMOTIONS = {"joy", "happy", "satisfied", "grateful", "relieved", "positive", "calm"}
        NEGATIVE_EMOTIONS = {"anger", "frustrated", "sad", "anxious", "disappointed", "negative", "fear"}

        positive_count = sum(
            count for emotion, count in emotion_dist.items()
            if emotion.lower() in POSITIVE_EMOTIONS
        )
        negative_count = sum(
            count for emotion, count in emotion_dist.items()
            if emotion.lower() in NEGATIVE_EMOTIONS
        )

        positive_ratio = (
            (positive_count / total_analyzed) if total_analyzed > 0 else 0.0
        )
        negative_ratio = (
            (negative_count / total_analyzed) if total_analyzed > 0 else 0.0
        )

        return {
            "avg_frustration_score": round(avg_frustration, 2),
            "emotion_distribution": dict(emotion_dist),
            "escalation_count": escalation_count,
            "total_analyzed": total_analyzed,
            "positive_ratio": round(positive_ratio, 4),
            "negative_ratio": round(negative_ratio, 4),
            "period_days": days,
        }

    except Exception as exc:
        # BC-008: never crash — return zero-values.
        import logging
        logging.getLogger("parwa.admin").exception(
            "admin_sentiment_failed: %s", exc
        )
        return {
            "avg_frustration_score": 0.0,
            "emotion_distribution": {},
            "escalation_count": 0,
            "total_analyzed": 0,
            "positive_ratio": 0.0,
            "negative_ratio": 0.0,
            "period_days": days,
            "error": "sentiment_calculation_failed",
        }
