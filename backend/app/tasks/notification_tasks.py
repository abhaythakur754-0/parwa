"""
Notification Celery Tasks (MF05)

Tasks for:
- Async notification dispatch
- Digest generation
- Batch notifications
- PS03/PS10 handlers
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from celery import shared_task
from sqlalchemy.orm import Session

from app.core.tenant_context import TenantContext
from app.services.notification_service import NotificationService
from app.services.notification_template_service import NotificationTemplateService
from app.services.notification_preference_service import NotificationPreferenceService
from database.base import get_db
from database.models.tickets import Ticket
from database.models.core import User
from database.models.remaining import Notification


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_notification_task(
    self,
    company_id: str,
    event_type: str,
    recipient_ids: List[str],
    data: Dict[str, Any],
    channels: Optional[List[str]] = None,
    priority: str = "medium",
    ticket_id: Optional[str] = None,
    sender_id: Optional[str] = None,
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Async notification dispatch task.
    
    Args:
        company_id: Company ID
        event_type: Event type
        recipient_ids: List of user IDs to notify
        data: Event data
        channels: Override channels
        priority: Notification priority
        ticket_id: Related ticket ID
        sender_id: User who triggered notification
        cc: CC email addresses
        bcc: BCC email addresses
        
    Returns:
        Dict with dispatch results
    """
    db = next(get_db())
    
    try:
        with TenantContext(company_id):
            service = NotificationService(db, company_id)
            
            result = service.send_notification(
                event_type=event_type,
                recipient_ids=recipient_ids,
                data=data,
                channels=channels,
                priority=priority,
                ticket_id=ticket_id,
                sender_id=sender_id,
                cc=cc,
                bcc=bcc,
            )
            
            return result
            
    except Exception as e:
        self.retry(exc=e)
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def send_bulk_notification_task(
    self,
    company_id: str,
    event_type: str,
    recipient_ids: List[str],
    data: Dict[str, Any],
    channels: Optional[List[str]] = None,
    batch_size: int = 100,
) -> Dict[str, Any]:
    """
    Async bulk notification task.
    
    Processes notifications in batches for PS10 incident notifications.
    """
    db = next(get_db())
    
    try:
        with TenantContext(company_id):
            service = NotificationService(db, company_id)
            
            result = service.send_bulk_notification(
                event_type=event_type,
                recipient_ids=recipient_ids,
                data=data,
                channels=channels,
                batch_size=batch_size,
            )
            
            return result
            
    except Exception as e:
        self.retry(exc=e)
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@shared_task
def notify_human_queue_task(
    company_id: str,
    ticket_id: str,
    summary: str,
    escalation_reason: str,
) -> Dict[str, Any]:
    """
    PS03: Notify human queue when client asks for human.
    
    Includes AI conversation summary.
    """
    db = next(get_db())
    
    try:
        with TenantContext(company_id):
            service = NotificationService(db, company_id)
            
            result = service.notify_human_queue(
                ticket_id=ticket_id,
                summary=summary,
                escalation_reason=escalation_reason,
            )
            
            return result
            
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@shared_task
def notify_incident_subscribers_task(
    company_id: str,
    incident_id: str,
    incident_title: str,
    status_update: str,
    affected_customer_ids: List[str],
) -> Dict[str, Any]:
    """
    PS10: Mass-notify all affected clients with incident status.
    """
    db = next(get_db())
    
    try:
        with TenantContext(company_id):
            service = NotificationService(db, company_id)
            
            result = service.notify_incident_subscribers(
                incident_id=incident_id,
                incident_title=incident_title,
                status_update=status_update,
                affected_customer_ids=affected_customer_ids,
            )
            
            return result
            
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@shared_task
def generate_daily_digest_task(
    company_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """
    Generate daily notification digest for a user.
    """
    db = next(get_db())
    
    try:
        with TenantContext(company_id):
            service = NotificationService(db, company_id)
            
            result = service.create_digest(
                user_id=user_id,
                period="daily",
            )
            
            if result.get("digest_created"):
                # Send digest notification
                digest = result.get("digest", {})
                
                # Create a summary notification
                send_notification_task.delay(
                    company_id=company_id,
                    event_type="digest",
                    recipient_ids=[user_id],
                    data={
                        "period": "daily",
                        "total_count": digest.get("total_count", 0),
                        "summary": digest.get("summary", ""),
                    },
                    channels=["email"],
                )
            
            return result
            
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@shared_task
def generate_weekly_digest_task(
    company_id: str,
    user_id: str,
) -> Dict[str, Any]:
    """
    Generate weekly notification digest for a user.
    """
    db = next(get_db())
    
    try:
        with TenantContext(company_id):
            service = NotificationService(db, company_id)
            
            result = service.create_digest(
                user_id=user_id,
                period="weekly",
            )
            
            if result.get("digest_created"):
                digest = result.get("digest", {})
                
                send_notification_task.delay(
                    company_id=company_id,
                    event_type="digest",
                    recipient_ids=[user_id],
                    data={
                        "period": "weekly",
                        "total_count": digest.get("total_count", 0),
                        "summary": digest.get("summary", ""),
                    },
                    channels=["email"],
                )
            
            return result
            
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@shared_task
def process_digest_queue_task(
    company_id: str,
    frequency: str = "daily",
) -> Dict[str, Any]:
    """
    Process all users who have opted into digest notifications.
    
    Called by Celery beat on schedule.
    """
    db = next(get_db())
    
    try:
        with TenantContext(company_id):
            pref_service = NotificationPreferenceService(db, company_id)
            
            # Get users with digest enabled
            users = db.query(User).filter(
                User.company_id == company_id,
                User.is_active == True,
            ).all()
            
            processed = 0
            
            for user in users:
                try:
                    metadata = json.loads(user.metadata_json or "{}")
                    digest_settings = metadata.get("digest_settings", {})
                    
                    if digest_settings.get("frequency") == frequency:
                        if frequency == "daily":
                            generate_daily_digest_task.delay(company_id, user.id)
                        else:
                            generate_weekly_digest_task.delay(company_id, user.id)
                        processed += 1
                        
                except Exception:
                    continue
            
            return {
                "success": True,
                "frequency": frequency,
                "processed_users": processed,
            }
            
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@shared_task
def cleanup_old_notifications_task(
    company_id: str,
    days_old: int = 90,
) -> Dict[str, Any]:
    """
    Cleanup notifications older than specified days.
    
    Called by Celery beat daily.
    """
    db = next(get_db())
    
    try:
        with TenantContext(company_id):
            cutoff = datetime.now(timezone.utc) - timedelta(days=days_old)
            
            # Delete read notifications older than cutoff
            deleted = db.query(Notification).filter(
                Notification.company_id == company_id,
                Notification.read_at.isnot(None),
                Notification.created_at < cutoff,
            ).delete()
            
            db.commit()
            
            return {
                "success": True,
                "deleted_count": deleted,
                "cutoff_date": cutoff.isoformat(),
            }
            
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@shared_task
def send_ticket_notification_task(
    company_id: str,
    ticket_id: str,
    event_type: str,
    additional_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Send notification for ticket event.
    
    Convenience task that fetches ticket data and sends notification.
    """
    db = next(get_db())
    
    try:
        with TenantContext(company_id):
            # Get ticket details
            ticket = db.query(Ticket).filter(
                Ticket.id == ticket_id,
                Ticket.company_id == company_id,
            ).first()
            
            if not ticket:
                return {"success": False, "error": "Ticket not found"}
            
            # Build notification data
            data = {
                "ticket_id": ticket_id,
                "ticket_subject": ticket.subject,
                "customer_id": ticket.customer_id,
                "priority": ticket.priority if hasattr(ticket, 'priority') else "medium",
                "category": ticket.category if hasattr(ticket, 'category') else "general",
                "status": ticket.status,
                "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
            }
            
            if additional_data:
                data.update(additional_data)
            
            # Determine recipients based on event type
            recipient_ids = []
            
            if event_type == "ticket_assigned" and ticket.assigned_to:
                recipient_ids = [ticket.assigned_to]
            elif event_type in ["ticket_resolved", "ticket_closed"]:
                # Notify customer
                if ticket.customer_id:
                    recipient_ids = [ticket.customer_id]
            else:
                # Notify assignee and watchers
                if ticket.assigned_to:
                    recipient_ids.append(ticket.assigned_to)
            
            if not recipient_ids:
                return {"success": True, "message": "No recipients for notification"}
            
            service = NotificationService(db, company_id)
            
            result = service.send_notification(
                event_type=event_type,
                recipient_ids=recipient_ids,
                data=data,
                ticket_id=ticket_id,
            )
            
            return result
            
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@shared_task
def send_sla_notification_task(
    company_id: str,
    ticket_id: str,
    notification_type: str,  # "warning" or "breached"
    time_remaining: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Send SLA warning or breach notification.
    """
    db = next(get_db())
    
    try:
        with TenantContext(company_id):
            ticket = db.query(Ticket).filter(
                Ticket.id == ticket_id,
                Ticket.company_id == company_id,
            ).first()
            
            if not ticket:
                return {"success": False, "error": "Ticket not found"}
            
            event_type = "sla_warning" if notification_type == "warning" else "sla_breached"
            
            data = {
                "ticket_id": ticket_id,
                "ticket_subject": ticket.subject,
                "sla_type": "first_response",  # or resolution depending on context
                "time_remaining": time_remaining or "0",
                "warning_level": "75%" if notification_type == "warning" else "100%",
            }
            
            # Notify assignee and managers
            recipient_ids = []
            
            if ticket.assigned_to:
                recipient_ids.append(ticket.assigned_to)
            
            # Add team leads/managers for SLA breaches
            if notification_type == "breached":
                managers = db.query(User).filter(
                    User.company_id == company_id,
                    User.role.in_(["admin", "manager"]),
                ).all()
                recipient_ids.extend([m.id for m in managers])
            
            if not recipient_ids:
                return {"success": True, "message": "No recipients"}
            
            service = NotificationService(db, company_id)
            
            result = service.send_notification(
                event_type=event_type,
                recipient_ids=list(set(recipient_ids)),
                data=data,
                priority="urgent" if notification_type == "breached" else "high",
                ticket_id=ticket_id,
            )
            
            return result
            
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@shared_task
def seed_default_templates_task(
    company_id: str,
) -> Dict[str, Any]:
    """
    Seed default notification templates for a company.
    
    Called when a new company is created.
    """
    db = next(get_db())
    
    try:
        with TenantContext(company_id):
            service = NotificationTemplateService(db, company_id)
            
            count = service.seed_default_templates()
            
            return {
                "success": True,
                "templates_created": count,
            }
            
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()
