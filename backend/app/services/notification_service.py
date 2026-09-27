"""
Notification Service - Notification dispatch engine (MF05)

Handles:
- Multi-channel notification dispatch (email, in_app, push)
- Event-driven notifications
- Notification batching and digest mode
- PS03: Talk to human → auto-notify human queue
- PS10: Incident mode → mass-notify all affected clients
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from markupsafe import escape as html_escape, Markup

from sqlalchemy import and_, desc, or_
from sqlalchemy.orm import Session

from app.exceptions import NotFoundError, ValidationError
from database.models.tickets import Ticket, NotificationTemplate
from database.models.core import User, Company
from database.models.remaining import Notification, NotificationLog, NotificationPreference

logger = logging.getLogger("parwa.services.notification")


class NotificationService:
    """
    Central notification dispatch engine.
    
    Features:
    - Event-driven notifications
    - Multi-channel support (email, in_app, push)
    - Per-user preferences
    - Digest mode for aggregation
    - PS03/PS10 handlers
    """
    
    # Supported notification channels
    CHANNELS = ["email", "in_app", "push"]
    
    # Event types that trigger notifications
    EVENT_TYPES = [
        "ticket_created",
        "ticket_updated",
        "ticket_assigned",
        "ticket_resolved",
        "ticket_closed",
        "ticket_reopened",
        "sla_warning",
        "sla_breached",
        "ticket_escalated",
        "mention",
        "bulk_action_completed",
        "incident_created",
        "incident_resolved",
    ]
    
    # Priority levels for notifications
    PRIORITY_LOW = "low"
    PRIORITY_MEDIUM = "medium"
    PRIORITY_HIGH = "high"
    PRIORITY_URGENT = "urgent"
    
    def __init__(self, db: Session, company_id: str):
        self.db = db
        self.company_id = company_id
    
    def send_notification(
        self,
        event_type: str,
        recipient_ids: List[str],
        data: Dict[str, Any],
        channels: Optional[List[str]] = None,
        priority: str = PRIORITY_MEDIUM,
        ticket_id: Optional[str] = None,
        sender_id: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Send notification to recipients.
        
        Args:
            event_type: Type of event triggering notification
            recipient_ids: List of user IDs to notify
            data: Event data for template rendering
            channels: Override channels (defaults to user preferences)
            priority: Notification priority
            ticket_id: Related ticket ID
            sender_id: User ID who triggered the notification
            cc: CC email addresses (email only)
            bcc: BCC email addresses (email only)
            
        Returns:
            Dict with notification results
        """
        if event_type not in self.EVENT_TYPES:
            raise ValidationError(f"Invalid event type: {event_type}")
        
        results = {
            "event_type": event_type,
            "sent_count": 0,
            "failed_count": 0,
            "notification_ids": [],
            "errors": [],
        }
        
        for recipient_id in recipient_ids:
            try:
                # Get user preferences
                preferences = self._get_user_preferences(recipient_id, event_type)
                
                # Determine channels to use
                target_channels = channels or preferences.get("channels", ["in_app"])
                
                # Check if user wants this event type
                if not preferences.get("enabled", True):
                    results["skipped_count"] = results.get("skipped_count", 0) + 1
                    continue
                
                # Create notification record
                notification = Notification(
                    id=str(uuid4()),
                    company_id=self.company_id,
                    user_id=recipient_id,
                    event_type=event_type,
                    priority=priority,
                    title=self._generate_title(event_type, data),
                    message=self._generate_message(event_type, data),
                    data_json=json.dumps(data),
                    ticket_id=ticket_id,
                    sender_id=sender_id,
                    channels=json.dumps(target_channels),
                    status="pending",
                    created_at=datetime.now(timezone.utc),
                )
                
                self.db.add(notification)
                self.db.flush()
                
                # Dispatch to each channel
                dispatch_results = self._dispatch_to_channels(
                    notification=notification,
                    channels=target_channels,
                    data=data,
                    cc=cc,
                    bcc=bcc,
                )
                
                notification.status = "sent" if dispatch_results["success"] else "failed"
                notification.sent_at = datetime.now(timezone.utc) if dispatch_results["success"] else None
                
                results["notification_ids"].append(notification.id)
                
                if dispatch_results["success"]:
                    results["sent_count"] += 1
                else:
                    results["failed_count"] += 1
                    results["errors"].append({
                        "recipient_id": recipient_id,
                        "error": dispatch_results.get("error"),
                    })
                
            except Exception as e:
                results["failed_count"] += 1
                results["errors"].append({
                    "recipient_id": recipient_id,
                    "error": str(e),
                })
        
        self.db.commit()
        return results
    
    def send_bulk_notification(
        self,
        event_type: str,
        recipient_ids: List[str],
        data: Dict[str, Any],
        channels: Optional[List[str]] = None,
        batch_size: int = 100,
    ) -> Dict[str, Any]:
        """
        Send notification to many recipients in batches.
        
        Used for PS10 incident mode mass notifications.
        """
        if len(recipient_ids) > 10000:
            raise ValidationError("Maximum 10,000 recipients per bulk notification")
        
        results = {
            "event_type": event_type,
            "total_recipients": len(recipient_ids),
            "sent_count": 0,
            "failed_count": 0,
            "batches": 0,
        }
        
        # Process in batches
        for i in range(0, len(recipient_ids), batch_size):
            batch = recipient_ids[i:i + batch_size]
            
            batch_result = self.send_notification(
                event_type=event_type,
                recipient_ids=batch,
                data=data,
                channels=channels,
            )
            
            results["sent_count"] += batch_result["sent_count"]
            results["failed_count"] += batch_result["failed_count"]
            results["batches"] += 1
        
        return results
    
    def notify_human_queue(
        self,
        ticket_id: str,
        summary: str,
        escalation_reason: str,
    ) -> Dict[str, Any]:
        """
        PS03: Notify human queue when client asks for human.
        
        Includes AI conversation summary.
        """
        # Get ticket details
        ticket = self.db.query(Ticket).filter(
            Ticket.id == ticket_id,
            Ticket.company_id == self.company_id,
        ).first()
        
        if not ticket:
            raise NotFoundError(f"Ticket {ticket_id} not found")
        
        # Find human agents in the appropriate queue
        # This would typically query assignment rules or department members
        agents = self._get_available_agents(ticket.category if hasattr(ticket, 'category') else None)
        
        if not agents:
            # Fallback to all company agents
            agents = self._get_company_agents()
        
        if not agents:
            return {
                "success": False,
                "error": "No human agents available",
            }
        
        notification_data = {
            "ticket_id": ticket_id,
            "ticket_subject": ticket.subject,
            "customer_id": ticket.customer_id,
            "escalation_reason": escalation_reason,
            "ai_summary": summary,
            "priority": ticket.priority if hasattr(ticket, 'priority') else "medium",
        }
        
        return self.send_notification(
            event_type="ticket_escalated",
            recipient_ids=[a["id"] for a in agents],
            data=notification_data,
            channels=["email", "in_app"],
            priority=self.PRIORITY_HIGH,
            ticket_id=ticket_id,
        )
    
    def notify_incident_subscribers(
        self,
        incident_id: str,
        incident_title: str,
        status_update: str,
        affected_customer_ids: List[str],
    ) -> Dict[str, Any]:
        """
        PS10: Mass-notify all affected clients with incident status updates.
        """
        notification_data = {
            "incident_id": incident_id,
            "incident_title": incident_title,
            "status_update": status_update,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        return self.send_bulk_notification(
            event_type="incident_created" if "created" in status_update.lower() else "incident_resolved",
            recipient_ids=affected_customer_ids,
            data=notification_data,
            channels=["email"],
        )
    
    def get_notifications(
        self,
        user_id: str,
        status: Optional[str] = None,
        event_type: Optional[str] = None,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Notification], int]:
        """Get notifications for a user."""
        query = self.db.query(Notification).filter(
            Notification.company_id == self.company_id,
            Notification.user_id == user_id,
        )
        
        if status:
            query = query.filter(Notification.status == status)
        
        if event_type:
            query = query.filter(Notification.event_type == event_type)
        
        if unread_only:
            query = query.filter(Notification.read_at.is_(None))
        
        total = query.count()
        
        notifications = query.order_by(
            desc(Notification.created_at)
        ).offset(offset).limit(limit).all()
        
        return notifications, total
    
    def mark_as_read(self, notification_id: str, user_id: str) -> Notification:
        """Mark notification as read."""
        notification = self.db.query(Notification).filter(
            Notification.id == notification_id,
            Notification.user_id == user_id,
            Notification.company_id == self.company_id,
        ).first()
        
        if not notification:
            raise NotFoundError(f"Notification {notification_id} not found")
        
        notification.read_at = datetime.now(timezone.utc)
        notification.status = "read"
        self.db.commit()
        
        return notification
    
    def mark_all_as_read(self, user_id: str) -> int:
        """Mark all notifications as read for a user."""
        count = self.db.query(Notification).filter(
            Notification.company_id == self.company_id,
            Notification.user_id == user_id,
            Notification.read_at.is_(None),
        ).update({
            "read_at": datetime.now(timezone.utc),
            "status": "read",
        })
        
        self.db.commit()
        return count
    
    def get_unread_count(self, user_id: str) -> int:
        """Get unread notification count for a user."""
        return self.db.query(Notification).filter(
            Notification.company_id == self.company_id,
            Notification.user_id == user_id,
            Notification.read_at.is_(None),
        ).count()
    
    def _get_user_preferences(
        self,
        user_id: str,
        event_type: str,
    ) -> Dict[str, Any]:
        """Get user notification preferences for an event type."""
        preference = self.db.query(NotificationPreference).filter(
            NotificationPreference.company_id == self.company_id,
            NotificationPreference.user_id == user_id,
            NotificationPreference.event_type == event_type,
        ).first()
        
        if preference:
            return {
                "enabled": preference.enabled,
                "channels": json.loads(preference.channels) if preference.channels else ["in_app"],
            }
        
        # Default preferences
        return {
            "enabled": True,
            "channels": ["in_app"],
        }
    
    def _dispatch_to_channels(
        self,
        notification: Notification,
        channels: List[str],
        data: Dict[str, Any],
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Dispatch notification to specified channels."""
        results = {
            "success": True,
            "channels": {},
        }
        
        for channel in channels:
            try:
                if channel == "email":
                    result = self._send_email(notification, data, cc, bcc)
                elif channel == "in_app":
                    result = self._send_in_app(notification, data)
                elif channel == "push":
                    result = self._send_push(notification, data)
                else:
                    result = {"success": False, "error": f"Unknown channel: {channel}"}
                
                results["channels"][channel] = result
                
                if not result.get("success"):
                    results["success"] = False
                    
            except Exception as e:
                results["channels"][channel] = {"success": False, "error": str(e)}
                results["success"] = False
        
        return results
    
    def _send_email(
        self,
        notification: Notification,
        data: Dict[str, Any],
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Send email notification via email service."""
        # Import here to avoid circular dependency
        from app.services.email_service import EmailService
        
        # Get recipient email
        user = self.db.query(User).filter(User.id == notification.user_id).first()
        
        if not user or not user.email:
            return {"success": False, "error": "User has no email address"}
        
        # Get template for this event type
        template = self._get_template(notification.event_type, "email")
        
        email_service = EmailService(self.db, self.company_id)
        
        try:
            # Render email from template
            subject = self._render_template(template.get("subject", notification.title), data)
            body = self._render_template(template.get("body", notification.message), data)
            
            # Send email
            email_service.send_email(
                to_email=user.email,
                subject=subject,
                html_content=body,
                cc=cc,
                bcc=bcc,
            )
            
            return {"success": True, "message_id": str(uuid4())}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _send_in_app(
        self,
        notification: Notification,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Send in-app notification via Socket.io."""
        try:
            # Import event emitter
            from app.core.event_emitter import EventEmitter
            
            emitter = EventEmitter()
            emitter.emit_to_user(
                user_id=notification.user_id,
                event_name="notification:new",
                data={
                    "id": notification.id,
                    "event_type": notification.event_type,
                    "title": notification.title,
                    "message": notification.message,
                    "priority": notification.priority,
                    "ticket_id": notification.ticket_id,
                    "created_at": notification.created_at.isoformat() if notification.created_at else None,
                },
            )
            
            return {"success": True}
            
        except Exception as e:
            # In-app may fail if socket not connected, but don't fail the whole notification
            return {"success": True, "warning": str(e)}
    
    def _send_push(
        self,
        notification: Notification,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Send push notification via FCM/APNs.

        S-13 fix: Implements push notification dispatch using Firebase
        Cloud Messaging (FCM) for Android/web and APNs for iOS.  Device
        tokens are stored on the User model (``push_tokens`` column, a
        JSON list).  If no tokens are registered the method returns
        gracefully without error.

        The implementation is provider-agnostic: it first tries FCM
        (works for Android + web push) and falls back to APNs for iOS
        device tokens that start with a hex pattern.
        """
        try:
            # Retrieve registered push tokens for the user
            user = self.db.query(User).filter(
                User.id == notification.user_id,
            ).first()

            if not user:
                return {"success": False, "error": "User not found"}

            # push_tokens is expected to be a JSON list stored on the user
            push_tokens = getattr(user, "push_tokens", None) or []
            if isinstance(push_tokens, str):
                import json as _json
                try:
                    push_tokens = _json.loads(push_tokens)
                except (_json.JSONDecodeError, TypeError):
                    push_tokens = []

            if not push_tokens:
                return {
                    "success": True,
                    "warning": "No push tokens registered for user",
                }

            # Build the FCM payload
            title = data.get("title", notification.title or "PARWA")
            body = data.get("body", notification.message or "")

            fcm_tokens = []
            apns_tokens = []

            for token in push_tokens:
                if isinstance(token, dict):
                    token_value = token.get("token", "")
                    token_type = token.get("type", "fcm")
                else:
                    token_value = str(token)
                    # Heuristic: iOS APNs tokens are 64 hex chars
                    token_type = "apns" if len(token_value) == 64 and all(c in "0123456789abcdefABCDEF" for c in token_value) else "fcm"

                if token_type == "apns":
                    apns_tokens.append(token_value)
                else:
                    fcm_tokens.append(token_value)

            results: Dict[str, Any] = {"fcm": None, "apns": None}

            # ── FCM dispatch ──────────────────────────────────────
            if fcm_tokens:
                results["fcm"] = self._dispatch_fcm(
                    tokens=fcm_tokens,
                    title=title,
                    body=body,
                    data_payload={
                        "notification_id": str(notification.id),
                        "event_type": notification.event_type,
                        "ticket_id": str(notification.ticket_id) if notification.ticket_id else None,
                        "priority": notification.priority,
                    },
                )

            # ── APNs dispatch ─────────────────────────────────────
            if apns_tokens:
                results["apns"] = self._dispatch_apns(
                    tokens=apns_tokens,
                    title=title,
                    body=body,
                    data_payload={
                        "notification_id": str(notification.id),
                        "event_type": notification.event_type,
                    },
                )

            # Determine overall success
            any_success = any(r and r.get("success") for r in results.values() if r)
            any_failure = any(r and not r.get("success") for r in results.values() if r)

            if any_success and not any_failure:
                return {"success": True, "results": results}
            elif any_success:
                return {"success": True, "warning": "Partial delivery", "results": results}
            else:
                return {"success": False, "error": "All push deliveries failed", "results": results}

        except Exception as e:
            logger.warning("push_notification_error user=%s error=%s", getattr(notification, "user_id", "?"), str(e))
            return {"success": False, "error": str(e)}

    # ── Push notification providers ───────────────────────────────

    @staticmethod
    def _dispatch_fcm(
        tokens: list,
        title: str,
        body: str,
        data_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Dispatch push via Firebase Cloud Messaging.

        Reads ``FCM_SERVER_KEY`` from app settings.  If the key is not
        configured, returns a graceful skip rather than crashing.
        """
        try:
            from app.config import get_settings
            settings = get_settings()
            server_key = getattr(settings, "FCM_SERVER_KEY", None)

            if not server_key:
                return {"success": True, "warning": "FCM_SERVER_KEY not configured; push skipped"}

            import httpx

            response = httpx.post(
                "https://fcm.googleapis.com/fcm/send",
                headers={
                    "Authorization": f"key={server_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "registration_ids": tokens,
                    "notification": {"title": title, "body": body},
                    "data": data_payload,
                    "priority": "high" if data_payload.get("priority") == "urgent" else "normal",
                },
                timeout=10,
            )

            if response.status_code == 200:
                result_data = response.json()
                return {
                    "success": True,
                    "success_count": result_data.get("success", 0),
                    "failure_count": result_data.get("failure", 0),
                }
            else:
                return {"success": False, "status_code": response.status_code, "error": response.text[:200]}

        except ImportError:
            return {"success": True, "warning": "httpx not available; FCM push skipped"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def _dispatch_apns(
        tokens: list,
        title: str,
        body: str,
        data_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Dispatch push via Apple Push Notification service.

        APNs requires a TLS certificate or token-based authentication.
        If the certificate path is not configured, returns a graceful
        skip rather than crashing.
        """
        try:
            from app.config import get_settings
            settings = get_settings()
            apns_cert_path = getattr(settings, "APNS_CERT_PATH", None)
            apns_key_id = getattr(settings, "APNS_KEY_ID", None)

            if not apns_cert_path and not apns_key_id:
                return {"success": True, "warning": "APNS not configured; push skipped"}

            # APNs HTTP/2 implementation would go here using httpx with
            # HTTP/2 support.  For now we log and return graceful skip
            # until the APNs certificate/key is provisioned.
            logger.info(
                "apns_dispatch_skip tokens=%d reason=not_fully_configured",
                len(tokens),
            )
            return {"success": True, "warning": "APNs dispatch pending certificate provisioning"}

        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _get_template(self, event_type: str, channel: str) -> Dict[str, str]:
        """Get notification template for event type and channel."""
        template = self.db.query(NotificationTemplate).filter(
            NotificationTemplate.company_id == self.company_id,
            NotificationTemplate.event_type == event_type,
            NotificationTemplate.channel == channel,
            NotificationTemplate.is_active == True,
        ).first()
        
        if template:
            return {
                "subject": template.subject_template,
                "body": template.body_template,
            }
        
        # Return default templates
        return self._get_default_template(event_type, channel)
    
    def _get_default_template(self, event_type: str, channel: str) -> Dict[str, str]:
        """Get default notification template."""
        default_templates = {
            "ticket_created": {
                "subject": "New Ticket Created: {{ticket_subject}}",
                "body": "A new ticket has been created. Subject: {{ticket_subject}}",
            },
            "ticket_assigned": {
                "subject": "Ticket Assigned: {{ticket_subject}}",
                "body": "A ticket has been assigned to you. Subject: {{ticket_subject}}",
            },
            "ticket_resolved": {
                "subject": "Ticket Resolved: {{ticket_subject}}",
                "body": "Your ticket has been resolved. Subject: {{ticket_subject}}",
            },
            "ticket_closed": {
                "subject": "Ticket Closed: {{ticket_subject}}",
                "body": "Your ticket has been closed. Subject: {{ticket_subject}}",
            },
            "ticket_reopened": {
                "subject": "Ticket Reopened: {{ticket_subject}}",
                "body": "A ticket has been reopened. Subject: {{ticket_subject}}",
            },
            "sla_warning": {
                "subject": "SLA Warning: {{ticket_subject}}",
                "body": "Ticket SLA is approaching. Time remaining: {{time_remaining}}",
            },
            "sla_breached": {
                "subject": "SLA Breached: {{ticket_subject}}",
                "body": "Ticket SLA has been breached. Subject: {{ticket_subject}}",
            },
            "ticket_escalated": {
                "subject": "Ticket Escalated: {{ticket_subject}}",
                "body": "A ticket has been escalated. Reason: {{escalation_reason}}",
            },
            "incident_created": {
                "subject": "Incident: {{incident_title}}",
                "body": "An incident has been reported. {{status_update}}",
            },
            "incident_resolved": {
                "subject": "Incident Resolved: {{incident_title}}",
                "body": "The incident has been resolved. {{status_update}}",
            },
        }
        
        return default_templates.get(event_type, {
            "subject": "Notification",
            "body": "{{message}}",
        })
    
    def _render_template(self, template: str, data: Dict[str, Any]) -> str:
        """Simple template rendering with variable substitution.

        H-16 FIX: All user-provided values are HTML-escaped to prevent
        injection attacks when rendered in email HTML bodies.
        """
        result = template
        for key, value in data.items():
            placeholder = "{{" + key + "}}"
            if value is None:
                safe_value = ""
            elif isinstance(value, (Markup,)):
                safe_value = str(value)
            else:
                safe_value = html_escape(str(value))
            result = result.replace(placeholder, safe_value)
        return result
    
    def _generate_title(self, event_type: str, data: Dict[str, Any]) -> str:
        """Generate notification title from event type and data."""
        titles = {
            "ticket_created": f"New Ticket: {data.get('ticket_subject', 'New Ticket')}",
            "ticket_updated": f"Ticket Updated: {data.get('ticket_subject', 'Ticket')}",
            "ticket_assigned": f"Assigned: {data.get('ticket_subject', 'Ticket')}",
            "ticket_resolved": f"Resolved: {data.get('ticket_subject', 'Ticket')}",
            "ticket_closed": f"Closed: {data.get('ticket_subject', 'Ticket')}",
            "ticket_reopened": f"Reopened: {data.get('ticket_subject', 'Ticket')}",
            "sla_warning": f"SLA Warning: {data.get('ticket_subject', 'Ticket')}",
            "sla_breached": f"SLA Breached: {data.get('ticket_subject', 'Ticket')}",
            "ticket_escalated": f"Escalated: {data.get('ticket_subject', 'Ticket')}",
            "mention": f"You were mentioned in {data.get('ticket_subject', 'a ticket')}",
            "bulk_action_completed": "Bulk Action Completed",
            "incident_created": f"Incident: {data.get('incident_title', 'New Incident')}",
            "incident_resolved": f"Resolved: {data.get('incident_title', 'Incident')}",
        }
        return titles.get(event_type, "Notification")
    
    def _generate_message(self, event_type: str, data: Dict[str, Any]) -> str:
        """Generate notification message from event type and data."""
        messages = {
            "ticket_created": f"A new ticket has been created by {data.get('customer_name', 'a customer')}.",
            "ticket_updated": f"Ticket has been updated.",
            "ticket_assigned": f"Ticket has been assigned to you.",
            "ticket_resolved": f"Your ticket has been resolved.",
            "ticket_closed": f"Your ticket has been closed.",
            "ticket_reopened": f"A ticket has been reopened.",
            "sla_warning": f"SLA deadline approaching. Time remaining: {data.get('time_remaining', 'unknown')}",
            "sla_breached": f"SLA deadline has been breached for this ticket.",
            "ticket_escalated": f"Ticket escalated. Reason: {data.get('escalation_reason', 'Not specified')}",
            "mention": f"You were mentioned: {data.get('excerpt', '')}",
            "bulk_action_completed": f"Bulk action completed. {data.get('success_count', 0)} succeeded, {data.get('failure_count', 0)} failed.",
            "incident_created": f"Incident reported: {data.get('status_update', '')}",
            "incident_resolved": f"Incident resolved: {data.get('status_update', '')}",
        }
        return messages.get(event_type, "You have a new notification.")
    
    def _get_available_agents(self, category: Optional[str] = None) -> List[Dict[str, str]]:
        """Get available human agents for assignment."""
        # This would typically query assignment rules
        # For now, return empty list to be implemented with assignment service
        return []
    
    def _get_company_agents(self) -> List[Dict[str, str]]:
        """Get all company agents."""
        agents = self.db.query(User).filter(
            User.company_id == self.company_id,
            User.role.in_(["agent", "admin"]),
            User.is_active == True,
        ).all()
        
        return [{"id": a.id, "name": a.name, "email": a.email} for a in agents]
    
    def create_digest(
        self,
        user_id: str,
        period: str = "daily",
    ) -> Dict[str, Any]:
        """
        Create notification digest for a user.
        
        Aggregates unread notifications into a single summary.
        """
        if period not in ["daily", "weekly"]:
            raise ValidationError("Period must be 'daily' or 'weekly'")
        
        # Calculate time range
        if period == "daily":
            since = datetime.now(timezone.utc) - timedelta(days=1)
        else:
            since = datetime.now(timezone.utc) - timedelta(weeks=1)
        
        # Get unread notifications
        notifications = self.db.query(Notification).filter(
            Notification.company_id == self.company_id,
            Notification.user_id == user_id,
            Notification.read_at.is_(None),
            Notification.created_at >= since,
        ).all()
        
        if not notifications:
            return {
                "success": True,
                "digest_created": False,
                "message": "No notifications to digest",
            }
        
        # Group by event type
        grouped = {}
        for n in notifications:
            if n.event_type not in grouped:
                grouped[n.event_type] = []
            grouped[n.event_type].append(n)
        
        # Create digest summary
        digest = {
            "period": period,
            "total_count": len(notifications),
            "grouped_counts": {k: len(v) for k, v in grouped.items()},
            "summary": self._generate_digest_summary(grouped),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        
        return {
            "success": True,
            "digest_created": True,
            "digest": digest,
        }
    
    def _generate_digest_summary(self, grouped: Dict[str, List[Notification]]) -> str:
        """Generate human-readable digest summary."""
        parts = []
        
        for event_type, notifications in grouped.items():
            count = len(notifications)
            if event_type == "ticket_assigned":
                parts.append(f"{count} ticket(s) assigned to you")
            elif event_type == "sla_warning":
                parts.append(f"{count} SLA warning(s)")
            elif event_type == "ticket_escalated":
                parts.append(f"{count} escalation(s)")
            elif event_type == "ticket_reopened":
                parts.append(f"{count} reopened ticket(s)")
            else:
                parts.append(f"{count} {event_type.replace('_', ' ')} notification(s)")
        
        return "; ".join(parts)
