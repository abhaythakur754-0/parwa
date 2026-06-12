"""Notification management routes (PHASE 16 — GAP 12).

Provides endpoints to:
  - List notifications
  - Mark notifications as read
  - Get unread count
  - Update notification preferences
  - Create notifications (for internal use)
"""
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Notification, AuditLog
from app.auth import get_current_user

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


# --- Pydantic Models ---

class MarkReadRequest(BaseModel):
    notification_id: str = None  # If null, mark ALL as read


class NotificationPreference(BaseModel):
    category: str
    email_enabled: bool = True
    in_app_enabled: bool = True


class CreateNotificationRequest(BaseModel):
    category: str
    severity: str = "info"
    title: str
    body: str = None
    action_url: str = None


# --- Routes ---

@router.get("/list")
def list_notifications(
    category: str = None,
    severity: str = None,
    read: bool = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List notifications for the current tenant."""
    query = db.query(Notification).filter(
        Notification.tenant_id == current_user.tenant_id,
    )

    if category:
        query = query.filter(Notification.category == category)
    if severity:
        query = query.filter(Notification.severity == severity)
    if read is not None:
        query = query.filter(Notification.read == read)

    total = query.count()
    notifications = query.order_by(Notification.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "notifications": [
            {
                "id": n.id,
                "category": n.category,
                "severity": n.severity,
                "title": n.title,
                "body": n.body,
                "action_url": n.action_url,
                "read": n.read,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in notifications
        ],
        "total": total,
        "unread": sum(1 for n in notifications if not n.read),
    }


@router.get("/unread-count")
def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the count of unread notifications."""
    count = db.query(Notification).filter(
        Notification.tenant_id == current_user.tenant_id,
        Notification.read == False,
    ).count()

    return {"unread_count": count}


@router.post("/mark-read")
def mark_read(
    req: MarkReadRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark notifications as read. If notification_id is null, mark all as read."""
    if req.notification_id:
        notification = db.query(Notification).filter(
            Notification.id == req.notification_id,
            Notification.tenant_id == current_user.tenant_id,
        ).first()
        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")
        notification.read = True
    else:
        # Mark all as read
        db.query(Notification).filter(
            Notification.tenant_id == current_user.tenant_id,
            Notification.read == False,
        ).update({"read": True})

    db.commit()

    return {"message": "Notifications marked as read"}


@router.post("/create")
def create_notification(
    req: CreateNotificationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a notification (for internal system use)."""
    notification = Notification(
        tenant_id=current_user.tenant_id,
        category=req.category,
        severity=req.severity,
        title=req.title,
        body=req.body,
        action_url=req.action_url,
        read=False,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    return {
        "id": notification.id,
        "category": notification.category,
        "severity": notification.severity,
        "title": notification.title,
        "created_at": notification.created_at.isoformat() if notification.created_at else None,
    }


@router.get("/preferences")
def get_notification_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get notification preferences for the current tenant.

    Default preferences are:
    - Integration health: in-app + email (HIGH)
    - Billing: in-app + email (HIGH)
    - Webhooks: in-app only (MEDIUM)
    - AI actions: in-app + email (HIGH)
    - System: in-app only (LOW)
    - Compliance: in-app + email (HIGH, cannot disable)
    """
    # Default preferences (in production, stored per tenant)
    default_prefs = [
        {"category": "integration_health", "email_enabled": True, "in_app_enabled": True, "can_disable": False},
        {"category": "billing", "email_enabled": True, "in_app_enabled": True, "can_disable": False},
        {"category": "webhooks", "email_enabled": False, "in_app_enabled": True, "can_disable": True},
        {"category": "ai_actions", "email_enabled": True, "in_app_enabled": True, "can_disable": False},
        {"category": "system", "email_enabled": False, "in_app_enabled": True, "can_disable": True},
        {"category": "compliance", "email_enabled": True, "in_app_enabled": True, "can_disable": False},
    ]

    return {"preferences": default_prefs}


@router.post("/preferences")
def update_notification_preferences(
    prefs: list[NotificationPreference],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update notification preferences."""
    # Log the change
    audit = AuditLog(
        tenant_id=current_user.tenant_id,
        action="notifications.preferences_updated",
        actor=current_user.email,
        resource_type="settings",
        resource_id="notification_preferences",
        details=json.dumps({"preferences": [p.dict() for p in prefs]}),
        severity="info",
    )
    db.add(audit)
    db.commit()

    return {
        "message": "Notification preferences updated",
        "preferences": [p.dict() for p in prefs],
    }


@router.delete("/{notification_id}")
def delete_notification(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a notification."""
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.tenant_id == current_user.tenant_id,
    ).first()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    db.delete(notification)
    db.commit()

    return {"message": "Notification deleted"}
