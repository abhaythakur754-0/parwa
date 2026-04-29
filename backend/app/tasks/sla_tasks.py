"""
PARWA SLA Celery Tasks - Day 29

Implements periodic tasks for SLA monitoring:
- run_sla_check: Monitor all active SLA timers (every 5 min)
- send_sla_warning: Notify when SLA approaching breach (PS17: 75%)
- send_sla_breach_notification: Notify when SLA breached (PS11)
- check_first_response_sla: Check first response SLA for tickets

These tasks implement:
- PS11: SLA breach detection and escalation
- PS17: SLA approaching warning (75% threshold)
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

from celery import shared_task

from app.tasks.base import ParwaTask
from database.base import SessionLocal
from database.models.tickets import (
    SLAPolicy,
    SLATimer,
    Ticket,
    TicketStatus,
    TicketPriority,
)

logger = logging.getLogger(__name__)


@shared_task(
    base=ParwaTask,
    bind=True,
    name="sla.run_sla_check",
    max_retries=3,
    soft_time_limit=55,
    time_limit=60,
)
def run_sla_check(self, company_id: str) -> Dict[str, Any]:
    """
    Check all active SLA timers for a company.

    Runs every 5 minutes via Beat schedule.

    Returns:
        Dict with counts of breaches detected and warnings sent.
    """
    logger.info(f"Running SLA check for company {company_id}")

    db = SessionLocal()

    try:
        # Get all active SLA timers
        active_timers = (
            db.query(SLATimer)
            .filter(
                SLATimer.company_id == company_id,
                SLATimer.is_breached is False,  # noqa: E712
                SLATimer.resolved_at == None,  # noqa: E711
            )
            .all()
        )

        breaches_detected = 0
        warnings_sent = 0

        for timer in active_timers:
            # Get the policy
            policy = (
                db.query(SLAPolicy)
                .filter(
                    SLAPolicy.id == timer.policy_id,
                )
                .first()
            )

            if not policy:
                continue

            # Get the ticket
            ticket = (
                db.query(Ticket)
                .filter(
                    Ticket.id == timer.ticket_id,
                )
                .first()
            )

            if not ticket or ticket.status in [
                TicketStatus.closed.value,
                TicketStatus.resolved.value,
            ]:
                continue

            now = datetime.now(timezone.utc)

            # Check first response SLA
            if not timer.first_response_at:
                first_response_deadline = timer.created_at + timedelta(
                    minutes=policy.first_response_minutes
                )
                if now > first_response_deadline:
                    # First response SLA breached
                    timer.is_breached = True
                    timer.breached_at = now
                    ticket.sla_breached = True
                    breaches_detected += 1

                    # Send breach notification
                    send_sla_breach_notification.delay(
                        company_id=company_id,
                        ticket_id=ticket.id,
                        breach_type="first_response",
                        time_elapsed_minutes=int(
                            (now - timer.created_at).total_seconds() / 60
                        ),
                    )

                    logger.warning(
                        f"First response SLA breached for ticket {ticket.id}"
                    )

            # Check resolution SLA
            resolution_deadline = timer.created_at + timedelta(
                minutes=policy.resolution_minutes
            )

            if now > resolution_deadline:
                # Resolution SLA breached
                if not timer.is_breached:
                    timer.is_breached = True
                    timer.breached_at = now
                    ticket.sla_breached = True
                    breaches_detected += 1

                    # Send breach notification
                    send_sla_breach_notification.delay(
                        company_id=company_id,
                        ticket_id=ticket.id,
                        breach_type="resolution",
                        time_elapsed_minutes=int(
                            (now - timer.created_at).total_seconds() / 60
                        ),
                    )

                    logger.warning(f"Resolution SLA breached for ticket {ticket.id}")

            # Check for approaching breach (75% threshold - PS17)
            else:
                total_seconds = policy.resolution_minutes * 60
                elapsed_seconds = (now - timer.created_at).total_seconds()
                percentage = elapsed_seconds / total_seconds

                if percentage >= 0.75:
                    # Send warning notification
                    warnings_sent += 1

                    send_sla_warning.delay(
                        company_id=company_id,
                        ticket_id=ticket.id,
                        percentage_elapsed=percentage,
                        minutes_remaining=int(
                            (resolution_deadline - now).total_seconds() / 60
                        ),
                    )

        db.commit()

        return {
            "company_id": company_id,
            "timers_checked": len(active_timers),
            "breaches_detected": breaches_detected,
            "warnings_sent": warnings_sent,
        }

    except Exception as e:
        logger.error(f"SLA check failed for company {company_id}: {e}")
        db.rollback()
        raise

    finally:
        db.close()


@shared_task(
    base=ParwaTask,
    bind=True,
    name="sla.send_sla_warning",
    max_retries=3,
    soft_time_limit=30,
    time_limit=35,
)
def send_sla_warning(
    self,
    company_id: str,
    ticket_id: str,
    percentage_elapsed: float,
    minutes_remaining: int,
) -> Dict[str, Any]:
    """
    Send SLA warning notification for a ticket approaching breach.

    PS17: Send warning at 75% of SLA time.

    This task triggers:
    - Email notification to assigned agent
    - Socket.io event for real-time warning
    - Optional Slack/Teams notification
    """
    logger.info(
        f"SLA warning for ticket {ticket_id}: "
        f"{percentage_elapsed * 100:.1f}% elapsed, "
        f"{minutes_remaining} minutes remaining"
    )

    db = SessionLocal()

    try:
        # Get ticket details
        ticket = (
            db.query(Ticket)
            .filter(
                Ticket.id == ticket_id,
                Ticket.company_id == company_id,
            )
            .first()
        )

        if not ticket:
            return {"sent": False, "reason": "ticket_not_found"}

        # Get assigned agent(s)
        assigned_to = ticket.assigned_to

        # In a real implementation, this would:
        # 1. Send email via Brevo to assigned agent
        # 2. Emit Socket.io event 'ticket:sla_warning'
        # 3. Log the warning for analytics

        # For now, we log and return success
        logger.info(f"SLA warning sent for ticket {ticket_id} to agent {assigned_to}")

        return {
            "sent": True,
            "ticket_id": ticket_id,
            "assigned_to": assigned_to,
            "percentage_elapsed": percentage_elapsed,
            "minutes_remaining": minutes_remaining,
        }

    finally:
        db.close()


@shared_task(
    base=ParwaTask,
    bind=True,
    name="sla.send_sla_breach_notification",
    max_retries=3,
    soft_time_limit=30,
    time_limit=35,
)
def send_sla_breach_notification(
    self,
    company_id: str,
    ticket_id: str,
    breach_type: str,  # first_response or resolution
    time_elapsed_minutes: int,
) -> Dict[str, Any]:
    """
    Send SLA breach notification.

    PS11: When SLA breaches:
    - Escalate ticket priority to critical
    - Notify management/lead agent
    - Mark ticket as breached

    This task triggers:
    - Urgent email notification
    - Socket.io event for real-time alert
    - Auto-escalation of priority
    """
    logger.warning(
        f"SLA breach ({breach_type}) for ticket {ticket_id} "
        f"after {time_elapsed_minutes} minutes"
    )

    db = SessionLocal()

    try:
        # Get ticket
        ticket = (
            db.query(Ticket)
            .filter(
                Ticket.id == ticket_id,
                Ticket.company_id == company_id,
            )
            .first()
        )

        if not ticket:
            return {"sent": False, "reason": "ticket_not_found"}

        # PS11: Escalate priority to critical
        if ticket.priority != TicketPriority.critical.value:
            old_priority = ticket.priority
            ticket.priority = TicketPriority.critical.value
            ticket.escalation_level = min((ticket.escalation_level or 1) + 1, 3)
            logger.info(
                f"Escalated ticket {ticket_id} priority from "
                f"{old_priority} to critical"
            )

        db.commit()

        # In a real implementation, this would:
        # 1. Send urgent email to assigned agent + manager
        # 2. Emit Socket.io event 'ticket:sla_breached'
        # 3. Create escalation log entry

        return {
            "sent": True,
            "ticket_id": ticket_id,
            "breach_type": breach_type,
            "time_elapsed_minutes": time_elapsed_minutes,
            "priority_escalated": True,
        }

    except Exception as e:
        logger.error(f"Failed to send breach notification: {e}")
        db.rollback()
        raise

    finally:
        db.close()


@shared_task(
    base=ParwaTask,
    bind=True,
    name="sla.check_first_response_sla",
    max_retries=3,
    soft_time_limit=30,
    time_limit=35,
)
def check_first_response_sla(
    self,
    company_id: str,
    ticket_id: str,
) -> Dict[str, Any]:
    """
    Check first response SLA for a specific ticket.

    Called after first response is recorded.
    """
    db = SessionLocal()

    try:
        timer = (
            db.query(SLATimer)
            .filter(
                SLATimer.ticket_id == ticket_id,
                SLATimer.company_id == company_id,
            )
            .first()
        )

        if not timer:
            return {"checked": False, "reason": "timer_not_found"}

        if not timer.first_response_at:
            return {"checked": False, "reason": "no_first_response"}

        policy = (
            db.query(SLAPolicy)
            .filter(
                SLAPolicy.id == timer.policy_id,
            )
            .first()
        )

        if not policy:
            return {"checked": False, "reason": "policy_not_found"}

        response_time = (
            timer.first_response_at - timer.created_at
        ).total_seconds() / 60

        if response_time > policy.first_response_minutes:
            # Breached
            timer.is_breached = True
            timer.breached_at = timer.first_response_at

            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            if ticket:
                ticket.sla_breached = True

            db.commit()

            return {
                "checked": True,
                "breached": True,
                "response_time_minutes": response_time,
                "threshold_minutes": policy.first_response_minutes,
            }

        return {
            "checked": True,
            "breached": False,
            "response_time_minutes": response_time,
            "threshold_minutes": policy.first_response_minutes,
        }

    finally:
        db.close()


@shared_task(
    base=ParwaTask,
    bind=True,
    name="sla.seed_sla_policies",
    max_retries=3,
    soft_time_limit=30,
    time_limit=35,
)
def seed_sla_policies(self, company_id: str) -> Dict[str, Any]:
    """
    Seed default SLA policies for a new company.

    Called when a new company is provisioned.
    """
    from app.services.sla_service import SLAService

    db = SessionLocal()

    try:
        service = SLAService(db)
        created = service.seed_default_policies(company_id)

        return {
            "seeded": True,
            "company_id": company_id,
            "policies_created": len(created),
        }

    except Exception as e:
        logger.error(f"Failed to seed SLA policies: {e}")
        return {
            "seeded": False,
            "company_id": company_id,
            "error": str(e),
        }

    finally:
        db.close()


@shared_task(
    base=ParwaTask,
    bind=True,
    name="sla.daily_sla_report",
    max_retries=3,
    soft_time_limit=120,
    time_limit=130,
)
def daily_sla_report(self, company_id: str) -> Dict[str, Any]:
    """
    Generate daily SLA report for a company.

    Runs daily via Beat schedule.
    """
    from app.services.sla_service import SLAService

    db = SessionLocal()

    try:
        service = SLAService(db)

        # Get stats for yesterday
        end_date = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        start_date = end_date - timedelta(days=1)

        stats = service.get_sla_stats(
            company_id=company_id,
            start_date=start_date,
            end_date=end_date,
        )

        # In a real implementation, this would:
        # 1. Generate PDF/HTML report
        # 2. Send email to company admins
        # 3. Store report in analytics DB

        logger.info(
            f"Daily SLA report for {company_id}: "
            f"{stats['compliant_count']}/{stats['total_tickets']} compliant, "
            f"{stats['breached_count']} breached"
        )

        return {
            "generated": True,
            "company_id": company_id,
            "date": start_date.isoformat(),
            "stats": stats,
        }

    finally:
        db.close()


# ── Part 13 Day 2: Company-wide SLA Tasks ───────────────────────────────


@shared_task(
    base=ParwaTask,
    bind=True,
    name="sla.check_all_company_slas",
    max_retries=3,
    soft_time_limit=55,
    time_limit=60,
)
def check_all_company_slas(self) -> Dict[str, Any]:
    """
    Check SLA timers for ALL active companies.

    Runs every minute via Beat schedule.
    Iterates through all active companies and triggers
    run_sla_check for each.
    """
    from database.models.core import Company

    db = SessionLocal()

    try:
        # Get all active companies
        active_companies = (
            db.query(Company)
            .filter(
                Company.status == "active",
            )
            .all()
        )

        companies_checked = 0
        total_breaches = 0
        total_warnings = 0

        for company in active_companies:
            try:
                # Trigger SLA check for this company
                result = run_sla_check(company_id=company.id)
                companies_checked += 1
                total_breaches += result.get("breaches_detected", 0)
                total_warnings += result.get("warnings_sent", 0)
            except Exception as e:
                logger.error(f"SLA check failed for company {company.id}: {e}")

        logger.info(
            f"SLA check complete: {companies_checked} companies, "
            f"{total_breaches} breaches, {total_warnings} warnings"
        )

        return {
            "companies_checked": companies_checked,
            "total_breaches": total_breaches,
            "total_warnings": total_warnings,
        }

    except Exception as e:
        logger.error(f"Failed to check all company SLAs: {e}")
        raise

    finally:
        db.close()


@shared_task(
    base=ParwaTask,
    bind=True,
    name="sla.daily_sla_report_all",
    max_retries=3,
    soft_time_limit=300,
    time_limit=330,
)
def daily_sla_report_all(self) -> Dict[str, Any]:
    """
    Generate daily SLA reports for ALL active companies.

    Runs daily at 6 AM UTC via Beat schedule.
    """
    from database.models.core import Company

    db = SessionLocal()

    try:
        # Get all active companies
        active_companies = (
            db.query(Company)
            .filter(
                Company.status == "active",
            )
            .all()
        )

        reports_generated = 0
        reports_failed = 0

        for company in active_companies:
            try:
                # Trigger daily report for this company
                daily_sla_report.delay(company_id=company.id)
                reports_generated += 1
            except Exception as e:
                logger.error(
                    f"Failed to queue SLA report for company {company.id}: {e}"
                )
                reports_failed += 1

        logger.info(
            "Daily SLA report queue complete: "
            f"{reports_generated} generated, {reports_failed} failed"
        )

        return {
            "reports_generated": reports_generated,
            "reports_failed": reports_failed,
        }

    except Exception as e:
        logger.error(f"Failed to queue daily SLA reports: {e}")
        raise

    finally:
        db.close()
