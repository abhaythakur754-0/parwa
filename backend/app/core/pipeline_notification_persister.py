"""
Pipeline Notification Persister — persists pipeline events to the notifications DB table.

When pipeline nodes emit events (ai:action_taken, ticket:delivered, ticket:escalated,
ticket:auto_resolved, ticket:knowledge_gap, ai:quality_low, ticket:routed), those events
go to Socket.io (real-time) + EventBuffer (Redis, temporary). But they're NOT persisted
to the `notifications` DB table — so if a human is offline when the event fires, they
never see it.

This module bridges that gap. It's called from event_emitter.emit_to_tenant (the single
chokepoint ALL events pass through) and creates a Notification row for each active user
in the tenant. The human sees the notification in NotificationBell when they come back
online, can click it to navigate to the right place, and can mark it as read.

BC-001: Notifications are scoped by company_id (tenant).
BC-012: Never crashes the emit pipeline — all errors are caught and logged.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

logger = logging.getLogger("parwa.event_persister")

# ── Event type → (title template, action_url template, priority) ──────
# Maps pipeline event types to human-readable titles + click-through URLs.
# The action_url determines WHERE the human lands when they click the notification.

EVENT_CONFIG: Dict[str, Dict[str, Any]] = {
    # P0 events
    "ai:action_taken": {
        "title": "AI took action",
        "url_template": "/dashboard/jarvis?ticket_id={ticket_id}",
        "priority": "medium",
        "message_template": "AI executed: {action}",
    },
    "ticket:delivered": {
        "title": "Response delivered",
        "url_template": "/dashboard/tickets/{ticket_id}",
        "priority": "medium",
        "message_template": "Delivered via {channel} — status: {status}",
    },
    "ticket:escalated": {
        "title": "Ticket escalated to human",
        "url_template": "/dashboard/escalations?ticket_id={ticket_id}",
        "priority": "urgent",
        "message_template": "AI quality {quality_score} below threshold. Needs human help.",
    },
    # P1 events
    "ticket:auto_resolved": {
        "title": "Ticket auto-resolved",
        "url_template": "/dashboard/tickets/{ticket_id}",
        "priority": "low",
        "message_template": "AI resolved this ticket automatically (confidence: {confidence})",
    },
    "ticket:knowledge_gap": {
        "title": "Knowledge gap detected",
        "url_template": "/dashboard/knowledge?ticket_id={ticket_id}",
        "priority": "medium",
        "message_template": "AI couldn't find enough knowledge for this {ticket_type} ticket",
    },
    "ai:quality_low": {
        "title": "Low AI quality score",
        "url_template": "/dashboard/jarvis?ticket_id={ticket_id}",
        "priority": "high",
        "message_template": "AI quality {quality_score} below threshold {quality_threshold}",
    },
    # P2 events
    "ticket:routed": {
        "title": "Surprising route decision",
        "url_template": "/dashboard/variants?ticket_id={ticket_id}",
        "priority": "low",
        "message_template": "Ticket routed to {selected_tier} — reason: {surprise_reason}",
    },
    # Agent lifecycle events (Node 1)
    "agent:creating": {
        "title": "AI agent being created",
        "url_template": "/dashboard/tickets/{ticket_id}",
        "priority": "medium",
        "message_template": "{message}",
    },
    "agent:limit_reached": {
        "title": "Agent limit reached — action needed",
        "url_template": "/dashboard/agents?ticket_id={ticket_id}",
        "priority": "high",
        "message_template": "{message}",
    },
    "agent:created": {
        "title": "New AI agent created",
        "url_template": "/dashboard/agents?ticket_id={ticket_id}",
        "priority": "medium",
        "message_template": "Agent for '{capability}' created successfully for ticket {ticket_id}.",
    },
    # Existing event types (persisted for completeness)
    "ticket:new": {
        "title": "New ticket",
        "url_template": "/dashboard/tickets/{ticket_id}",
        "priority": "medium",
        "message_template": "New ticket: {ticket_id}",
    },
    "ticket:resolved": {
        "title": "Ticket resolved",
        "url_template": "/dashboard/tickets/{ticket_id}",
        "priority": "low",
        "message_template": "Ticket resolved: {ticket_id}",
    },
}


def persist_pipeline_notification(
    company_id: str,
    event_type: str,
    payload: Dict[str, Any],
) -> None:
    """Persist a pipeline event as a Notification row for each tenant user.

    Called from event_emitter.emit_to_tenant so ALL registered pipeline events
    get persisted automatically. Creates one Notification row per active user
    in the tenant (role: owner, admin, agent).

    BC-001: Scoped by company_id.
    BC-012: Never raises — all errors are caught and logged.

    Args:
        company_id: Tenant identifier.
        event_type: Event type string (e.g. "ticket:escalated").
        payload: Event payload dict (must contain ticket_id for URL generation).
    """
    # Only persist pipeline events we have config for.
    config = EVENT_CONFIG.get(event_type)
    if config is None:
        return  # Not a pipeline event — skip (other events are handled by their emitters)

    try:
        from database.base import SessionLocal
        from database.models.core import User
        from database.models.remaining import Notification

        db = SessionLocal()
        try:
            # Find all active users in this tenant who should see pipeline notifications.
            # Include owner, admin, and agent roles. Exclude inactive users.
            users = (
                db.query(User)
                .filter(
                    User.company_id == company_id,
                    User.is_active == True,  # noqa: E712
                    User.role.in_(["owner", "admin", "agent"]),
                )
                .all()
            )

            if not users:
                # No users to notify — nothing to do.
                return

            # Build the notification fields from config + payload.
            ticket_id = payload.get("ticket_id", "")

            # Format the title + message using payload values.
            try:
                title = config["title"]
                message = config["message_template"].format(**payload)
            except (KeyError, IndexError):
                title = config["title"]
                message = json.dumps(payload)[:500]

            # Build the action_url using the ticket_id.
            try:
                action_url = config["url_template"].format(ticket_id=ticket_id, **payload)
            except (KeyError, IndexError):
                action_url = config["url_template"].format(ticket_id=ticket_id)

            priority = config.get("priority", "medium")

            # Create one notification per user.
            now = datetime.now(timezone.utc)
            for user in users:
                notification = Notification(
                    id=str(uuid4()),
                    company_id=company_id,
                    user_id=user.id,
                    event_type=event_type,
                    priority=priority,
                    title=title,
                    message=message,
                    data_json=json.dumps(payload, default=str),
                    ticket_id=ticket_id if ticket_id else None,
                    action_url=action_url,
                    channels=json.dumps(["in_app"]),
                    status="sent",
                    sent_at=now,
                    created_at=now,
                )
                db.add(notification)

            db.commit()
            logger.info(
                "pipeline_notification_persisted",
                extra={
                    "company_id": company_id,
                    "event_type": event_type,
                    "ticket_id": ticket_id,
                    "recipients": len(users),
                },
            )
        finally:
            db.close()
    except Exception as exc:
        # BC-012: Never crash the emit pipeline.
        logger.warning(
            "pipeline_notification_persist_failed",
            extra={
                "company_id": company_id,
                "event_type": event_type,
                "error": str(exc)[:300],
            },
        )
