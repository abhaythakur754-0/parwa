"""
PARWA Phase 3 — Notification API Routes

Endpoints for listing, reading, and managing notifications and preferences.

CRITICAL RULES:
- BC-001: All endpoints use company_id from JWT/header for tenant isolation
- BC-008: Never crash — all route handlers in try/except
- Critical notifications (payment_failed, pii_breach) cannot be disabled
- No mock data, no placeholder emails
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.deps import get_current_company_id, get_audit_trail
from app.core.notification_engine import NotificationEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/notifications", tags=["notifications"])

# ---------------------------------------------------------------------------
# Shared engine instance
# ---------------------------------------------------------------------------

_notification_engine = NotificationEngine()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class UpdatePreferencesRequest(BaseModel):
    """Update notification preferences for the company."""
    preferences: Dict[str, Any] = Field(
        ...,
        description=(
            "Dict of {category.severity: {email: bool, in_app: bool}}. "
            "Critical events (billing.payment_failed, compliance.pii_breach) cannot be disabled."
        ),
    )


# ---------------------------------------------------------------------------
# GET /notifications
# ---------------------------------------------------------------------------

@router.get("")
def list_notifications(
    unread_only: bool = Query(False, description="Only return unread notifications"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(50, ge=1, le=200, description="Max notifications to return"),
    company_id: str = Depends(get_current_company_id),
) -> dict:
    """List notifications for the company.

    BC-001: Scoped to company_id. BC-008: Never crashes.
    """
    try:
        notifications = _notification_engine.get_notifications(
            company_id=company_id,
            unread_only=unread_only,
            category=category,
            limit=limit,
        )
        return {
            "status": "success",
            "company_id": company_id,
            "total": len(notifications),
            "unread_only": unread_only,
            "category": category,
            "notifications": notifications,
        }
    except Exception as exc:
        logger.error("list_notifications failed for company_id=%s: %s", company_id, exc)
        return {
            "status": "error",
            "error": str(exc),
            "company_id": company_id,
            "notifications": [],
        }


# ---------------------------------------------------------------------------
# GET /notifications/unread-count
# ---------------------------------------------------------------------------

@router.get("/unread-count")
def get_unread_count(
    company_id: str = Depends(get_current_company_id),
) -> dict:
    """Get unread notification count for bell icon badge.

    BC-001: Scoped to company_id. BC-008: Never crashes.
    """
    try:
        count = _notification_engine.get_unread_count(company_id)
        return {
            "status": "success",
            "company_id": company_id,
            "unread_count": count,
        }
    except Exception as exc:
        logger.error("get_unread_count failed for company_id=%s: %s", company_id, exc)
        return {
            "status": "error",
            "error": str(exc),
            "company_id": company_id,
            "unread_count": 0,
        }


# ---------------------------------------------------------------------------
# POST /notifications/{notification_id}/read
# ---------------------------------------------------------------------------

@router.post("/{notification_id}/read")
def mark_notification_read(
    notification_id: str,
    company_id: str = Depends(get_current_company_id),
) -> dict:
    """Mark a single notification as read.

    BC-001: Scoped to company_id. BC-008: Never crashes.
    """
    try:
        success = _notification_engine.mark_read(
            notification_id=notification_id,
            company_id=company_id,
        )
        return {
            "status": "success" if success else "error",
            "company_id": company_id,
            "notification_id": notification_id,
            "message": (
                "Notification marked as read"
                if success
                else "Notification not found or already read"
            ),
        }
    except Exception as exc:
        logger.error(
            "mark_notification_read failed for company_id=%s notification_id=%s: %s",
            company_id, notification_id, exc,
        )
        return {
            "status": "error",
            "error": str(exc),
            "company_id": company_id,
            "notification_id": notification_id,
        }


# ---------------------------------------------------------------------------
# POST /notifications/read-all
# ---------------------------------------------------------------------------

@router.post("/read-all")
def mark_all_notifications_read(
    company_id: str = Depends(get_current_company_id),
) -> dict:
    """Mark all notifications as read for the company.

    BC-001: Scoped to company_id. BC-008: Never crashes.
    """
    try:
        count = _notification_engine.mark_all_read(company_id)
        return {
            "status": "success",
            "company_id": company_id,
            "marked_count": count,
            "message": f"Marked {count} notifications as read",
        }
    except Exception as exc:
        logger.error("mark_all_notifications_read failed for company_id=%s: %s", company_id, exc)
        return {
            "status": "error",
            "error": str(exc),
            "company_id": company_id,
            "marked_count": 0,
        }


# ---------------------------------------------------------------------------
# PUT /notifications/preferences
# ---------------------------------------------------------------------------

@router.put("/preferences")
def update_notification_preferences(
    body: UpdatePreferencesRequest,
    company_id: str = Depends(get_current_company_id),
) -> dict:
    """Update notification preferences for the company.

    Critical notifications (billing.payment_failed, compliance.pii_breach)
    cannot be disabled for either channel.

    BC-001: Scoped to company_id. BC-008: Never crashes.
    """
    try:
        result = _notification_engine.update_preferences(
            company_id=company_id,
            preferences=body.preferences,
        )

        # Audit log
        try:
            audit = get_audit_trail()
            if audit:
                audit.log_action(
                    company_id=company_id,
                    user_id="api_user",
                    action="update_notification_preferences",
                    tool="notifications",
                    details={"keys_updated": list(body.preferences.keys())},
                    outcome="success" if result.get("status") == "success" else "failure",
                )
        except Exception:
            pass

        return {
            "status": result.get("status", "error"),
            "company_id": company_id,
            "preferences": result.get("preferences", {}),
        }
    except Exception as exc:
        logger.error(
            "update_notification_preferences failed for company_id=%s: %s",
            company_id, exc,
        )
        return {
            "status": "error",
            "error": str(exc),
            "company_id": company_id,
        }


# ---------------------------------------------------------------------------
# GET /notifications/daily-summary
# ---------------------------------------------------------------------------

@router.get("/daily-summary")
def get_daily_summary(
    company_id: str = Depends(get_current_company_id),
) -> dict:
    """Get daily summary of notifications.

    BC-001: Scoped to company_id. BC-008: Never crashes.
    """
    try:
        summary = _notification_engine.get_daily_summary(company_id)
        return {
            "status": "success",
            "company_id": company_id,
            "summary": summary,
        }
    except Exception as exc:
        logger.error("get_daily_summary failed for company_id=%s: %s", company_id, exc)
        return {
            "status": "error",
            "error": str(exc),
            "company_id": company_id,
            "summary": {},
        }
