"""
Ticket Lifecycle Celery Tasks (Day 32)

Celery tasks for:
- Stale ticket detection and handling (PS06)
- Awaiting client reminders (PS08)
- Frozen ticket cleanup (PS07)
- Spam detection (PS15)
- Incident notifications (PS10)
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from celery import shared_task
from sqlalchemy.orm import Session

from app.core.tenant_context import TenantContext
from database.base import get_db
from database.models.tickets import Ticket, TicketStatus
from database.models.core import User


@shared_task
def detect_stale_tickets_task(
    company_id: str,
) -> Dict[str, Any]:
    """
    PS06: Detect and flag stale tickets.
    
    Called by Celery beat every 30 minutes.
    """
    db = next(get_db())
    
    try:
        with TenantContext(company_id):
            from app.services.stale_ticket_service import StaleTicketService
            
            service = StaleTicketService(db, company_id)
            
            # Get stale candidates
            stale_tickets = service.detect_stale_tickets()
            
            # Mark as stale
            marked_count = 0
            for stale_info in stale_tickets:
                if stale_info["staleness_level"] in ["timeout", "double_timeout"]:
                    try:
                        service.mark_as_stale(stale_info["ticket_id"])
                        marked_count += 1
                    except Exception:
                        continue
            
            return {
                "success": True,
                "detected_count": len(stale_tickets),
                "marked_count": marked_count,
            }
            
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@shared_task
def auto_close_stale_tickets_task(
    company_id: str,
) -> Dict[str, Any]:
    """
    PS06: Auto-close stale tickets after double timeout.
    
    Called by Celery beat daily.
    """
    db = next(get_db())
    
    try:
        with TenantContext(company_id):
            from app.services.stale_ticket_service import StaleTicketService
            
            service = StaleTicketService(db, company_id)
            
            # Get auto-close candidates
            candidates = service.get_auto_close_candidates()
            
            closed_count = 0
            for ticket in candidates:
                try:
                    service.auto_close_stale(ticket.id)
                    closed_count += 1
                except Exception:
                    continue
            
            return {
                "success": True,
                "closed_count": closed_count,
            }
            
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@shared_task
def send_awaiting_client_reminders_task(
    company_id: str,
) -> Dict[str, Any]:
    """
    PS08: Send reminders for tickets awaiting client response.
    
    Called by Celery beat every hour.
    """
    db = next(get_db())
    
    try:
        with TenantContext(company_id):
            from app.services.ticket_lifecycle_service import TicketLifecycleService
            
            service = TicketLifecycleService(db, company_id)
            
            # Get tickets needing reminders
            reminders = service.get_awaiting_client_tickets_for_reminder()
            
            sent_count = 0
            
            # Send 24h reminders
            for ticket_id in reminders["24h"]:
                try:
                    service.send_awaiting_client_reminder(ticket_id, "24h")
                    sent_count += 1
                except Exception:
                    continue
            
            # Send 7d reminders
            for ticket_id in reminders["7d"]:
                try:
                    service.send_awaiting_client_reminder(ticket_id, "7d")
                    sent_count += 1
                except Exception:
                    continue
            
            # Send 14d reminders (final warning)
            for ticket_id in reminders["14d"]:
                try:
                    service.send_awaiting_client_reminder(ticket_id, "14d")
                    sent_count += 1
                except Exception:
                    continue
            
            return {
                "success": True,
                "sent_count": sent_count,
                "by_type": {
                    "24h": len(reminders["24h"]),
                    "7d": len(reminders["7d"]),
                    "14d": len(reminders["14d"]),
                },
            }
            
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@shared_task
def cleanup_frozen_tickets_task(
    company_id: str,
    days_frozen: int = 30,
) -> Dict[str, Any]:
    """
    PS07: Cleanup frozen tickets older than 30 days.
    
    Called by Celery beat daily.
    """
    db = next(get_db())
    
    try:
        with TenantContext(company_id):
            from app.services.ticket_lifecycle_service import TicketLifecycleService
            
            service = TicketLifecycleService(db, company_id)
            
            result = service.cleanup_frozen_tickets(days_frozen)
            
            return {
                "success": True,
                "closed_count": result["closed_count"],
            }
            
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@shared_task
def detect_spam_patterns_task(
    company_id: str,
    time_window_hours: int = 24,
) -> Dict[str, Any]:
    """
    PS15: Analyze recent tickets for spam patterns.
    
    Called by Celery beat daily.
    """
    db = next(get_db())
    
    try:
        with TenantContext(company_id):
            from app.services.spam_detection_service import SpamDetectionService
            
            service = SpamDetectionService(db, company_id)
            
            patterns = service.detect_spam_patterns(time_window_hours)
            
            # Auto-flag high-confidence spam
            auto_flagged = 0
            
            for customer_info in patterns["patterns"]["high_frequency_customers"]:
                if customer_info["ticket_count"] > 20:  # Very high frequency
                    # Get customer's recent tickets
                    recent = db.query(Ticket).filter(
                        Ticket.company_id == company_id,
                        Ticket.customer_id == customer_info["customer_id"],
                        Ticket.is_spam == False,
                    ).all()
                    
                    for ticket in recent:
                        try:
                            analysis = service.analyze_ticket(
                                subject=ticket.subject or "",
                                content="",  # Would get from messages
                                customer_id=ticket.customer_id,
                            )
                            
                            if analysis["should_auto_flag"]:
                                service.mark_as_spam(
                                    ticket_id=ticket.id,
                                    reason="auto_detected_high_frequency",
                                )
                                auto_flagged += 1
                        except Exception:
                            continue
            
            return {
                "success": True,
                "patterns_detected": patterns,
                "auto_flagged": auto_flagged,
            }
            
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@shared_task
def escalate_ticket_task(
    company_id: str,
    ticket_id: str,
    escalation_reason: str,
    ai_summary: Optional[str] = None,
) -> Dict[str, Any]:
    """
    PS02/PS03: Escalate ticket to human.
    """
    db = next(get_db())
    
    try:
        with TenantContext(company_id):
            from app.services.ticket_lifecycle_service import TicketLifecycleService
            
            service = TicketLifecycleService(db, company_id)
            
            if escalation_reason == "human_request":
                result = service.handle_human_request(
                    ticket_id=ticket_id,
                    ai_summary=ai_summary or "",
                )
            else:
                result = service.handle_ai_cant_solve(
                    ticket_id=ticket_id,
                    attempt_count=3,  # Default attempt count
                    reason=escalation_reason,
                )
            
            return {
                "success": True,
                "escalation": result,
            }
            
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@shared_task
def notify_incident_update_task(
    company_id: str,
    incident_id: str,
    status_update: str,
) -> Dict[str, Any]:
    """
    PS10: Send incident update notifications.
    """
    db = next(get_db())
    
    try:
        with TenantContext(company_id):
            from app.services.incident_service import IncidentService
            
            service = IncidentService(db, company_id)
            
            result = service.notify_affected_customers(
                incident_id=incident_id,
                message=status_update,
            )
            
            return {
                "success": True,
                "notification_result": result,
            }
            
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@shared_task
def handle_variant_status_change_task(
    company_id: str,
    variant_id: str,
    is_online: bool,
) -> Dict[str, Any]:
    """
    PS13: Handle variant going offline or coming back online.
    """
    db = next(get_db())
    
    try:
        with TenantContext(company_id):
            from app.services.ticket_lifecycle_service import TicketLifecycleService
            
            service = TicketLifecycleService(db, company_id)
            
            if is_online:
                result = service.handle_variant_up(variant_id)
            else:
                result = service.handle_variant_down(variant_id)
            
            return {
                "success": True,
                "variant_id": variant_id,
                "is_online": is_online,
                "affected_tickets": result.get("queued_tickets") or result.get("resumed_tickets", 0),
            }
            
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@shared_task
def run_lifecycle_checks_task(
    company_id: str,
) -> Dict[str, Any]:
    """
    Run all periodic lifecycle checks for a company.
    
    Called by Celery beat every 5 minutes.
    """
    results = {
        "company_id": company_id,
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "checks": {},
    }
    
    # Run stale detection
    stale_result = detect_stale_tickets_task.delay(company_id)
    results["checks"]["stale_detection"] = {"queued": True}
    
    # Run awaiting client reminders
    reminders_result = send_awaiting_client_reminders_task.delay(company_id)
    results["checks"]["awaiting_client_reminders"] = {"queued": True}
    
    return results


@shared_task
def company_daily_maintenance_task(
    company_id: str,
) -> Dict[str, Any]:
    """
    Run daily maintenance tasks for a company.
    
    Called by Celery beat daily at midnight.
    """
    results = {
        "company_id": company_id,
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "tasks": {},
    }
    
    # Cleanup frozen tickets
    frozen_result = cleanup_frozen_tickets_task.delay(company_id)
    results["tasks"]["frozen_cleanup"] = {"queued": True}
    
    # Auto-close stale tickets
    stale_result = auto_close_stale_tickets_task.delay(company_id)
    results["tasks"]["stale_auto_close"] = {"queued": True}
    
    # Detect spam patterns
    spam_result = detect_spam_patterns_task.delay(company_id)
    results["tasks"]["spam_detection"] = {"queued": True}
    
    return results
