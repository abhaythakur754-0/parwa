"""
Notification API Endpoints (MF05)

Endpoints for:
- Notification listing and management
- Template CRUD
- Preference management
- Manual notification triggering
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_tenant_context, require_roles
from app.services.notification_service import NotificationService
from app.services.notification_template_service import NotificationTemplateService
from app.services.notification_preference_service import NotificationPreferenceService
from database.models.core import User


router = APIRouter(prefix="/notifications", tags=["Notifications"])


# ── Request/Response Schemas ────────────────────────────────────────────

class NotificationSendRequest(BaseModel):
    """Request to send a notification."""
    event_type: str = Field(...,
                            description="Event type triggering notification")
    recipient_ids: List[str] = Field(..., description="User IDs to notify")
    data: Dict[str, Any] = Field(
        default_factory=dict, description="Event data")
    channels: Optional[List[str]] = Field(
        None, description="Override channels")
    priority: str = Field(
        default="medium",
        description="Notification priority")
    ticket_id: Optional[str] = Field(None, description="Related ticket ID")
    cc: Optional[List[str]] = Field(None, description="CC email addresses")
    bcc: Optional[List[str]] = Field(None, description="BCC email addresses")


class NotificationMarkReadRequest(BaseModel):
    """Request to mark notifications as read."""
    notification_ids: Optional[List[str]] = Field(
        None, description="Specific notification IDs")
    mark_all: bool = Field(default=False, description="Mark all as read")


class PreferenceUpdateRequest(BaseModel):
    """Request to update notification preference."""
    enabled: Optional[bool] = Field(
        None, description="Whether notifications enabled")
    channels: Optional[List[str]] = Field(None, description="Channels to use")
    priority_threshold: Optional[str] = Field(
        None, description="Minimum priority")


class PreferencesBulkUpdateRequest(BaseModel):
    """Request to update multiple preferences."""
    preferences: Dict[str, Dict[str, Any]
                      ] = Field(..., description="Event type -> settings")


class DigestSettingsRequest(BaseModel):
    """Request to set digest settings."""
    frequency: str = Field(..., description="'none', 'daily', or 'weekly'")
    digest_time: str = Field(
        default="09:00",
        description="Time for digest (HH:MM)")


class TemplateCreateRequest(BaseModel):
    """Request to create a notification template."""
    event_type: str = Field(..., description="Event type for template")
    channel: str = Field(..., description="Channel: email, in_app, push")
    subject_template: str = Field(..., description="Subject template")
    body_template: str = Field(..., description="Body template")
    name: Optional[str] = Field(None, description="Template name")
    description: Optional[str] = Field(
        None, description="Template description")
    is_active: bool = Field(
        default=True,
        description="Whether template is active")


class TemplateUpdateRequest(BaseModel):
    """Request to update a notification template."""
    subject_template: Optional[str] = Field(None)
    body_template: Optional[str] = Field(None)
    name: Optional[str] = Field(None)
    description: Optional[str] = Field(None)
    is_active: Optional[bool] = Field(None)


class TemplatePreviewRequest(BaseModel):
    """Request to preview a template."""
    sample_data: Optional[Dict[str, Any]] = Field(
        None, description="Sample data for preview")


# ── Notification Endpoints ──────────────────────────────────────────────

@router.get("")
async def list_notifications(
    status: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    unread_only: bool = Query(False),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """List notifications for current user."""
    service = NotificationService(db, tenant["company_id"])

    notifications, total = service.get_notifications(
        user_id=current_user.id,
        status=status,
        event_type=event_type,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )

    return {
        "notifications": [
            {
                "id": n.id,
                "event_type": n.event_type,
                "title": n.title,
                "message": n.message,
                "priority": n.priority,
                "status": n.status,
                "ticket_id": n.ticket_id,
                "read_at": n.read_at.isoformat() if n.read_at else None,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in notifications
        ],
        "total": total,
        "unread_count": service.get_unread_count(current_user.id),
    }


@router.get("/unread-count")
async def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """Get unread notification count."""
    service = NotificationService(db, tenant["company_id"])

    return {
        "unread_count": service.get_unread_count(current_user.id),
    }


@router.post("/mark-read")
async def mark_notifications_read(
    request: NotificationMarkReadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """Mark notifications as read."""
    service = NotificationService(db, tenant["company_id"])

    if request.mark_all:
        count = service.mark_all_as_read(current_user.id)
        return {"marked_count": count, "marked_all": True}

    if not request.notification_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either notification_ids or mark_all required"
        )

    marked = []
    for notification_id in request.notification_ids:
        try:
            notification = service.mark_as_read(
                notification_id, current_user.id)
            marked.append(notification.id)
        except Exception:
            pass

    return {"marked_count": len(marked), "marked_ids": marked}


@router.post("/send")
async def send_notification(
    request: NotificationSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """Manually trigger a notification."""
    service = NotificationService(db, tenant["company_id"])

    result = service.send_notification(
        event_type=request.event_type,
        recipient_ids=request.recipient_ids,
        data=request.data,
        channels=request.channels,
        priority=request.priority,
        ticket_id=request.ticket_id,
        sender_id=current_user.id,
        cc=request.cc,
        bcc=request.bcc,
    )

    return result


@router.post("/digest")
async def create_digest(
    period: str = Query("daily", regex="^(daily|weekly)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """Create notification digest for current user."""
    service = NotificationService(db, tenant["company_id"])

    result = service.create_digest(
        user_id=current_user.id,
        period=period,
    )

    return result


# ── Template Endpoints ──────────────────────────────────────────────────

@router.get("/templates")
async def list_templates(
    event_type: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """List notification templates."""
    service = NotificationTemplateService(db, tenant["company_id"])

    templates, total = service.list_templates(
        event_type=event_type,
        channel=channel,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )

    return {
        "templates": [
            {
                "id": t.id,
                "event_type": t.event_type,
                "channel": t.channel,
                "name": t.name,
                "description": t.description,
                "subject_template": t.subject_template,
                "body_template": t.body_template,
                "is_active": t.is_active,
                "version": t.version,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            }
            for t in templates
        ],
        "total": total,
    }


@router.post("/templates")
async def create_template(
    request: TemplateCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
    tenant: Dict = Depends(get_tenant_context),
):
    """Create a notification template."""
    service = NotificationTemplateService(db, tenant["company_id"])

    try:
        template = service.create_template(
            event_type=request.event_type,
            channel=request.channel,
            subject_template=request.subject_template,
            body_template=request.body_template,
            name=request.name,
            description=request.description,
            is_active=request.is_active,
        )

        return {
            "id": template.id,
            "event_type": template.event_type,
            "channel": template.channel,
            "name": template.name,
            "is_active": template.is_active,
            "version": template.version,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/templates/{template_id}")
async def get_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """Get notification template by ID."""
    service = NotificationTemplateService(db, tenant["company_id"])

    try:
        template = service.get_template(template_id)

        return {
            "id": template.id,
            "event_type": template.event_type,
            "channel": template.channel,
            "name": template.name,
            "description": template.description,
            "subject_template": template.subject_template,
            "body_template": template.body_template,
            "is_active": template.is_active,
            "version": template.version,
            "created_at": template.created_at.isoformat() if template.created_at else None,
            "updated_at": template.updated_at.isoformat() if template.updated_at else None,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.put("/templates/{template_id}")
async def update_template(
    template_id: str,
    request: TemplateUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
    tenant: Dict = Depends(get_tenant_context),
):
    """Update notification template."""
    service = NotificationTemplateService(db, tenant["company_id"])

    try:
        template = service.update_template(
            template_id=template_id,
            subject_template=request.subject_template,
            body_template=request.body_template,
            name=request.name,
            description=request.description,
            is_active=request.is_active,
        )

        return {
            "id": template.id,
            "name": template.name,
            "is_active": template.is_active,
            "updated_at": template.updated_at.isoformat() if template.updated_at else None,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("owner", "admin")),
    tenant: Dict = Depends(get_tenant_context),
):
    """Delete notification template."""
    service = NotificationTemplateService(db, tenant["company_id"])

    try:
        service.delete_template(template_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/templates/{template_id}/preview")
async def preview_template(
    template_id: str,
    request: TemplatePreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """Preview a template with sample data."""
    service = NotificationTemplateService(db, tenant["company_id"])

    try:
        preview = service.preview_template(
            template_id=template_id,
            sample_data=request.sample_data,
        )

        return preview
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/templates/variables/{event_type}")
async def get_template_variables(
    event_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """Get valid variables for an event type."""
    service = NotificationTemplateService(db, tenant["company_id"])

    variables = service.get_template_variables(event_type)

    return {
        "event_type": event_type,
        "variables": variables,
    }


# ── Preference Endpoints ────────────────────────────────────────────────

@router.get("/preferences")
async def get_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """Get notification preferences for current user."""
    service = NotificationPreferenceService(db, tenant["company_id"])

    return service.get_user_preferences(current_user.id)


@router.put("/preferences/{event_type}")
async def update_preference(
    event_type: str,
    request: PreferenceUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """Update preference for an event type."""
    service = NotificationPreferenceService(db, tenant["company_id"])

    try:
        preference = service.update_preference(
            user_id=current_user.id,
            event_type=event_type,
            enabled=request.enabled,
            channels=request.channels,
            priority_threshold=request.priority_threshold,
        )

        return {
            "event_type": preference.event_type,
            "enabled": preference.enabled,
            "channels": preference.channels,
            "priority_threshold": preference.priority_threshold,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put("/preferences")
async def update_preferences_bulk(
    request: PreferencesBulkUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """Update multiple preferences at once."""
    service = NotificationPreferenceService(db, tenant["company_id"])

    result = service.update_preferences_bulk(
        user_id=current_user.id,
        preferences=request.preferences,
    )

    return result


@router.put("/preferences/digest")
async def set_digest_settings(
    request: DigestSettingsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """Set digest mode settings."""
    service = NotificationPreferenceService(db, tenant["company_id"])

    try:
        result = service.set_digest_settings(
            user_id=current_user.id,
            frequency=request.frequency,
            digest_time=request.digest_time,
        )

        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/preferences/reset")
async def reset_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """Reset preferences to defaults."""
    service = NotificationPreferenceService(db, tenant["company_id"])

    count = service.reset_to_defaults(current_user.id)

    return {"reset_count": count}


@router.post("/preferences/disable-all")
async def disable_all_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """Disable all notifications."""
    service = NotificationPreferenceService(db, tenant["company_id"])

    count = service.disable_all_notifications(current_user.id)

    return {"disabled_count": count}


@router.post("/preferences/enable-all")
async def enable_all_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant: Dict = Depends(get_tenant_context),
):
    """Enable all notifications with defaults."""
    service = NotificationPreferenceService(db, tenant["company_id"])

    count = service.enable_all_notifications(current_user.id)

    return {"enabled_count": count}
