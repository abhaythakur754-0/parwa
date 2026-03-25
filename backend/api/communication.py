"""
Communication API Endpoints

API endpoints for client communication including messages, templates,
and scheduled notifications.
"""
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.app.dependencies import get_db, get_current_user


router = APIRouter(prefix="/communication", tags=["Communication"])


# ============ Schemas ============

class SendMessageRequest(BaseModel):
    """Request to send a message."""
    client_id: str = Field(..., description="Client identifier")
    channel: str = Field(..., description="Communication channel")
    message_type: str = Field(..., description="Type of message")
    subject: str = Field(..., description="Message subject")
    body: str = Field(..., description="Message body")
    template_id: Optional[str] = Field(None, description="Template ID if using template")
    metadata: Optional[dict] = Field(default_factory=dict)


class ScheduleMessageRequest(BaseModel):
    """Request to schedule a message."""
    client_id: str = Field(..., description="Client identifier")
    channel: str = Field(..., description="Communication channel")
    subject: str = Field(..., description="Message subject")
    body: str = Field(..., description="Message body")
    scheduled_for: datetime = Field(..., description="When to send")
    timezone: str = Field("UTC", description="Client timezone")
    recurrence: str = Field("none", description="Recurrence type")
    metadata: Optional[dict] = Field(default_factory=dict)


class BatchScheduleRequest(BaseModel):
    """Request to batch schedule messages."""
    client_ids: List[str] = Field(..., description="List of client IDs")
    channel: str = Field(..., description="Communication channel")
    subject: str = Field(..., description="Message subject")
    body: str = Field(..., description="Message body")
    scheduled_for: datetime = Field(..., description="When to send")
    stagger_minutes: int = Field(5, description="Minutes to stagger between clients")


class MessageResponse(BaseModel):
    """Response for a message."""
    message_id: str
    client_id: str
    channel: str
    message_type: str
    status: str
    subject: str
    created_at: datetime
    sent_at: Optional[datetime] = None
    read_at: Optional[datetime] = None


class TemplateResponse(BaseModel):
    """Response for a template."""
    template_id: str
    name: str
    category: str
    subject_template: str
    body_template: str
    variables: List[str]
    channel: str
    is_active: bool


class ScheduledNotificationResponse(BaseModel):
    """Response for a scheduled notification."""
    schedule_id: str
    client_id: str
    channel: str
    subject: str
    scheduled_for: datetime
    status: str
    recurrence: str


class PreferenceUpdateRequest(BaseModel):
    """Request to update preferences."""
    email_enabled: Optional[bool] = None
    in_app_enabled: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    preferred_channel: Optional[str] = None
    quiet_hours_start: Optional[int] = None
    quiet_hours_end: Optional[int] = None
    frequency_cap_daily: Optional[int] = None


# ============ Message Endpoints ============

@router.get("/messages/{client_id}", response_model=List[MessageResponse])
async def get_client_messages(
    client_id: str,
    limit: int = Query(50, ge=1, le=100),
    channel: Optional[str] = None,
    current_user = Depends(get_current_user)
):
    """
    Get messages for a client.

    Args:
        client_id: Client identifier
        limit: Maximum messages to return
        channel: Optional filter by channel
    """
    from backend.services.client_success.communication_hub import (
        CommunicationHub, MessageChannel
    )

    hub = CommunicationHub()
    channel_enum = MessageChannel(channel) if channel else None

    messages = hub.get_message_history(
        client_id=client_id,
        limit=limit,
        channel=channel_enum
    )

    return [
        MessageResponse(
            message_id=m.message_id,
            client_id=m.client_id,
            channel=m.channel.value,
            message_type=m.message_type.value,
            status=m.status.value,
            subject=m.subject,
            created_at=m.created_at,
            sent_at=m.sent_at,
            read_at=m.read_at,
        )
        for m in messages
    ]


@router.post("/send", response_model=MessageResponse)
async def send_message(
    request: SendMessageRequest,
    current_user = Depends(get_current_user)
):
    """
    Send a message to a client.

    Sends immediately via the specified channel.
    """
    from backend.services.client_success.communication_hub import (
        CommunicationHub, MessageChannel, MessageType
    )

    hub = CommunicationHub()

    try:
        channel = MessageChannel(request.channel.lower())
        message_type = MessageType(request.message_type.lower())
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid channel or message type: {e}"
        )

    message = await hub.send_message(
        client_id=request.client_id,
        channel=channel,
        message_type=message_type,
        subject=request.subject,
        body=request.body,
        template_id=request.template_id,
        metadata=request.metadata
    )

    return MessageResponse(
        message_id=message.message_id,
        client_id=message.client_id,
        channel=message.channel.value,
        message_type=message.message_type.value,
        status=message.status.value,
        subject=message.subject,
        created_at=message.created_at,
        sent_at=message.sent_at,
        read_at=message.read_at,
    )


@router.post("/messages/{message_id}/read")
async def mark_message_read(
    message_id: str,
    current_user = Depends(get_current_user)
):
    """Mark a message as read."""
    from backend.services.client_success.communication_hub import CommunicationHub

    hub = CommunicationHub()
    message = hub.mark_read(message_id)

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message not found"
        )

    return {"status": "read", "message_id": message_id}


# ============ Schedule Endpoints ============

@router.post("/schedule", response_model=ScheduledNotificationResponse)
async def schedule_message(
    request: ScheduleMessageRequest,
    current_user = Depends(get_current_user)
):
    """
    Schedule a message for future delivery.

    Supports recurring notifications.
    """
    from backend.services.client_success.notification_scheduler import (
        NotificationScheduler, RecurrenceType
    )

    scheduler = NotificationScheduler()

    try:
        recurrence = RecurrenceType(request.recurrence.lower())
    except ValueError:
        recurrence = RecurrenceType.NONE

    notification = scheduler.schedule_notification(
        client_id=request.client_id,
        channel=request.channel,
        subject=request.subject,
        body=request.body,
        scheduled_for=request.scheduled_for,
        timezone=request.timezone,
        recurrence=recurrence,
        metadata=request.metadata
    )

    return ScheduledNotificationResponse(
        schedule_id=notification.schedule_id,
        client_id=notification.client_id,
        channel=notification.channel,
        subject=notification.subject,
        scheduled_for=notification.scheduled_for,
        status=notification.status.value,
        recurrence=notification.recurrence.value,
    )


@router.post("/schedule/batch")
async def batch_schedule_messages(
    request: BatchScheduleRequest,
    current_user = Depends(get_current_user)
):
    """Schedule messages for multiple clients."""
    from backend.services.client_success.notification_scheduler import NotificationScheduler

    scheduler = NotificationScheduler()

    results = scheduler.batch_schedule(
        client_ids=request.client_ids,
        channel=request.channel,
        subject=request.subject,
        body=request.body,
        scheduled_for=request.scheduled_for,
        stagger_minutes=request.stagger_minutes
    )

    return {
        "scheduled_count": len(results),
        "schedule_ids": [r.schedule_id for r in results.values()]
    }


@router.delete("/schedule/{schedule_id}")
async def cancel_schedule(
    schedule_id: str,
    current_user = Depends(get_current_user)
):
    """Cancel a scheduled notification."""
    from backend.services.client_success.notification_scheduler import NotificationScheduler

    scheduler = NotificationScheduler()
    notification = scheduler.cancel_schedule(schedule_id)

    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule not found or already sent"
        )

    return {"status": "cancelled", "schedule_id": schedule_id}


# ============ Template Endpoints ============

@router.get("/templates", response_model=List[TemplateResponse])
async def get_templates(
    category: Optional[str] = None,
    active_only: bool = True,
    current_user = Depends(get_current_user)
):
    """
    Get message templates.

    Args:
        category: Optional filter by category
        active_only: Only return active templates
    """
    from backend.services.client_success.message_templates import (
        MessageTemplates, TemplateCategory
    )

    templates = MessageTemplates()

    if category:
        try:
            cat = TemplateCategory(category.lower())
            result = templates.get_templates_by_category(cat)
        except ValueError:
            result = templates.get_all_templates()
    else:
        result = templates.get_active_templates() if active_only else templates.get_all_templates()

    return [
        TemplateResponse(
            template_id=t.template_id,
            name=t.name,
            category=t.category.value,
            subject_template=t.subject_template,
            body_template=t.body_template,
            variables=t.variables,
            channel=t.channel,
            is_active=t.is_active,
        )
        for t in result
    ]


@router.post("/templates/{template_id}/render")
async def render_template(
    template_id: str,
    variables: dict,
    current_user = Depends(get_current_user)
):
    """Render a template with variables."""
    from backend.services.client_success.message_templates import MessageTemplates

    templates = MessageTemplates()

    try:
        rendered = templates.render_template(template_id, variables)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    return rendered


# ============ Preference Endpoints ============

@router.get("/preferences/{client_id}")
async def get_preferences(
    client_id: str,
    current_user = Depends(get_current_user)
):
    """Get communication preferences for a client."""
    from backend.services.client_success.communication_hub import CommunicationHub

    hub = CommunicationHub()
    prefs = hub.get_preferences(client_id)

    return {
        "client_id": prefs.client_id,
        "email_enabled": prefs.email_enabled,
        "in_app_enabled": prefs.in_app_enabled,
        "sms_enabled": prefs.sms_enabled,
        "slack_enabled": prefs.slack_enabled,
        "preferred_channel": prefs.preferred_channel.value,
        "quiet_hours_start": prefs.quiet_hours_start,
        "quiet_hours_end": prefs.quiet_hours_end,
        "frequency_cap_daily": prefs.frequency_cap_daily,
    }


@router.put("/preferences/{client_id}")
async def update_preferences(
    client_id: str,
    request: PreferenceUpdateRequest,
    current_user = Depends(get_current_user)
):
    """Update communication preferences for a client."""
    from backend.services.client_success.communication_hub import (
        CommunicationHub, MessageChannel
    )

    hub = CommunicationHub()

    updates = request.model_dump(exclude_unset=True)

    if "preferred_channel" in updates and updates["preferred_channel"]:
        try:
            updates["preferred_channel"] = MessageChannel(updates["preferred_channel"].lower())
        except ValueError:
            del updates["preferred_channel"]

    prefs = hub.update_preferences(client_id, updates)

    return {
        "status": "updated",
        "client_id": client_id,
        "preferences": {
            "email_enabled": prefs.email_enabled,
            "in_app_enabled": prefs.in_app_enabled,
            "sms_enabled": prefs.sms_enabled,
            "preferred_channel": prefs.preferred_channel.value,
        }
    }


# ============ Summary Endpoints ============

@router.get("/summary")
async def get_communication_summary(
    current_user = Depends(get_current_user)
):
    """Get communication summary."""
    from backend.services.client_success.communication_hub import CommunicationHub

    hub = CommunicationHub()
    summary = hub.get_communication_summary()

    return summary
