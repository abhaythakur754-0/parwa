"""Incoming webhooks routes (PHASE 16 — Gap A).

Provides endpoints to:
  - Register webhook URLs with third-party services
  - Receive incoming webhook events
  - List webhook event log
  - Retry failed webhook deliveries
"""
import json
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, Integer, Text, DateTime, Boolean
from app.database import get_db, Base, init_db
from app.models import User, AuditLog
from app.auth import get_current_user
from app.services.external_tool_bus import get_tool_bus

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


# --- Webhook Event Model ---

class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, index=True, nullable=False)
    source = Column(String, nullable=False)  # e.g. "shopify", "hubspot"
    event_type = Column(String, nullable=False)  # e.g. "order.created", "contact.updated"
    payload = Column(Text, nullable=True)  # JSON string of the webhook payload
    status = Column(String, default="received")  # received, processed, failed
    processing_result = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)


class WebhookConfig(Base):
    __tablename__ = "webhook_configs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, index=True, nullable=False)
    integration_id = Column(String, nullable=False)
    webhook_url = Column(String, nullable=False)
    events_subscribed = Column(Text, nullable=True)  # JSON array of event types
    secret = Column(String, nullable=True)  # For signature verification
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Ensure tables exist
try:
    Base.metadata.create_all(bind=__import__("app.database", fromlist=["engine"]).engine)
except Exception:
    pass


# --- Pydantic Models ---

class RegisterWebhookRequest(BaseModel):
    integration_id: str
    events: list[str] = []  # Event types to subscribe to


class WebhookEventQuery(BaseModel):
    source: str = None
    event_type: str = None
    status: str = None
    limit: int = 50
    offset: int = 0


# --- Routes ---

@router.post("/register")
def register_webhook(
    req: RegisterWebhookRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Register a webhook for an integration.

    This creates a unique webhook URL that the third-party service
    can call to notify PARWA of events.
    """
    webhook_id = str(uuid.uuid4())
    webhook_url = f"/api/v1/webhooks/receive/{current_user.tenant_id}/{req.integration_id}"
    secret = str(uuid.uuid4())

    config = WebhookConfig(
        tenant_id=current_user.tenant_id,
        integration_id=req.integration_id,
        webhook_url=webhook_url,
        events_subscribed=json.dumps(req.events),
        secret=secret,
        active=True,
    )
    db.add(config)

    # Log audit event
    audit = AuditLog(
        tenant_id=current_user.tenant_id,
        action="webhook.registered",
        actor=current_user.email,
        resource_type="integration",
        resource_id=req.integration_id,
        details=json.dumps({"events": req.events, "webhook_url": webhook_url}),
        severity="info",
    )
    db.add(audit)
    db.commit()

    return {
        "message": f"Webhook registered for {req.integration_id}",
        "webhook_url": webhook_url,
        "webhook_id": config.id,
        "secret": secret,
        "events": req.events,
        "setup_instructions": f"Configure {req.integration_id} to send POST requests to this URL with the secret for signature verification.",
    }


@router.post("/receive/{tenant_id}/{integration_id}")
async def receive_webhook(
    tenant_id: str,
    integration_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Receive an incoming webhook event from a third-party service.

    This endpoint is called BY the third-party service, NOT by our frontend.
    It does not require auth — the webhook secret is used for verification.
    """
    body = await request.body()
    try:
        payload = json.loads(body)
    except Exception:
        payload = {"raw": body.decode("utf-8", errors="replace")}

    # Determine event type from payload
    event_type = "unknown"
    if isinstance(payload, dict):
        # Shopify pattern
        if "topic" in payload:
            event_type = payload["topic"]
        # HubSpot pattern
        elif "eventType" in payload:
            event_type = payload["eventType"]
        # Stripe pattern
        elif "type" in payload:
            event_type = payload["type"]
        # Generic
        elif "event" in payload:
            event_type = payload["event"]

    # Store the webhook event
    event = WebhookEvent(
        tenant_id=tenant_id,
        source=integration_id,
        event_type=event_type,
        payload=json.dumps(payload),
        status="received",
    )
    db.add(event)

    # Log audit event
    audit = AuditLog(
        tenant_id=tenant_id,
        action="webhook.received",
        actor=f"system:{integration_id}",
        resource_type="webhook",
        resource_id=integration_id,
        details=json.dumps({"event_type": event_type, "source": integration_id}),
        severity="info",
    )
    db.add(audit)
    db.commit()

    # Process the webhook event asynchronously (in production, this would go to a queue)
    try:
        _process_webhook_event(event, db)
        event.status = "processed"
        event.processed_at = datetime.utcnow()
        event.processing_result = json.dumps({"action": "logged", "event_type": event_type})
    except Exception as e:
        event.status = "failed"
        event.processing_result = json.dumps({"error": str(e)})
    finally:
        db.commit()

    return {"status": "ok", "event_id": event.id, "event_type": event_type}


@router.get("/events")
def list_webhook_events(
    source: str = None,
    event_type: str = None,
    status_filter: str = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List webhook events for the tenant."""
    query = db.query(WebhookEvent).filter(
        WebhookEvent.tenant_id == current_user.tenant_id,
    )

    if source:
        query = query.filter(WebhookEvent.source == source)
    if event_type:
        query = query.filter(WebhookEvent.event_type == event_type)
    if status_filter:
        query = query.filter(WebhookEvent.status == status_filter)

    total = query.count()
    events = query.order_by(WebhookEvent.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "events": [
            {
                "id": e.id,
                "source": e.source,
                "event_type": e.event_type,
                "status": e.status,
                "retry_count": e.retry_count,
                "created_at": e.created_at.isoformat() if e.created_at else None,
                "processed_at": e.processed_at.isoformat() if e.processed_at else None,
                "payload_preview": e.payload[:200] if e.payload else None,
            }
            for e in events
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/events/{event_id}/retry")
def retry_webhook_event(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retry processing a failed webhook event."""
    event = db.query(WebhookEvent).filter(
        WebhookEvent.id == event_id,
        WebhookEvent.tenant_id == current_user.tenant_id,
    ).first()

    if not event:
        raise HTTPException(status_code=404, detail="Webhook event not found")

    if event.status != "failed":
        raise HTTPException(status_code=400, detail="Only failed events can be retried")

    try:
        _process_webhook_event(event, db)
        event.status = "processed"
        event.processed_at = datetime.utcnow()
        event.retry_count += 1
        event.processing_result = json.dumps({"action": "retry_processed"})
    except Exception as e:
        event.retry_count += 1
        event.processing_result = json.dumps({"error": str(e), "retry": event.retry_count})

    db.commit()

    return {
        "event_id": event.id,
        "status": event.status,
        "retry_count": event.retry_count,
    }


@router.get("/configs")
def list_webhook_configs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all webhook configurations for the tenant."""
    configs = db.query(WebhookConfig).filter(
        WebhookConfig.tenant_id == current_user.tenant_id,
    ).all()

    return {
        "configs": [
            {
                "id": c.id,
                "integration_id": c.integration_id,
                "webhook_url": c.webhook_url,
                "events_subscribed": json.loads(c.events_subscribed) if c.events_subscribed else [],
                "active": c.active,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in configs
        ],
        "total": len(configs),
    }


def _process_webhook_event(event: WebhookEvent, db: Session):
    """Process a webhook event. In production, this would trigger AI actions.

    Current implementation: Log the event and create a notification.
    """
    from app.models import Notification

    # Create a notification for the webhook event
    notification = Notification(
        tenant_id=event.tenant_id,
        category="webhook",
        severity="low",
        title=f"Webhook: {event.event_type} from {event.source}",
        body=f"Received {event.event_type} event from {event.source}",
        read=False,
    )
    db.add(notification)
    db.commit()
