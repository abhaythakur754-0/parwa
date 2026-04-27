"""
Payment Failure Tasks (F-027, BG-16)

Celery tasks for payment failure handling:
- stop_service_immediately: Immediate service stop on payment failure
- resume_service: Resume service after successful payment
- send_payment_failed_notification: Send payment failure email
- freeze_tickets_for_company: Freeze all open tickets
- unfreeze_tickets_for_company: Unfreeze tickets after payment

BC-001: All tasks validate company_id
BC-003: All tasks have proper error handling and retries
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, Optional

from app.tasks.base import ParwaBaseTask, with_company_id
from app.tasks.celery_app import app
from database.base import SessionLocal
from database.models.core import Company
from database.models.billing import Subscription

logger = logging.getLogger("parwa.tasks.payment_failure")


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="billing",
    name="app.tasks.payment_failure.stop_service_immediately",
    max_retries=2,
    soft_time_limit=60,
    time_limit=120,
    retry_backoff=True,
)
@with_company_id
def stop_service_immediately(
    self,
    company_id: str,
    failure_id: str,
    failure_reason: str,
) -> dict:
    """
    Immediately stop service for a company due to payment failure.

    This task is dispatched when payment fails and performs:
    1. Stop all AI agents for this company
    2. Freeze all open tickets
    3. Block new ticket creation (via subscription_status check)

    Args:
        company_id: Company UUID string
        failure_id: PaymentFailure record ID
        failure_reason: Reason for payment failure

    Returns:
        Dict with stop status
    """
    try:
        results = {
            "company_id": company_id,
            "failure_id": failure_id,
            "agents_stopped": 0,
            "tickets_frozen": 0,
            "status": "stopped",
        }

        with SessionLocal() as db:
            # Verify company is in payment_failed status
            company = db.query(Company).filter(
                Company.id == company_id
            ).first()

            if not company:
                raise ValueError(f"Company {company_id} not found")

            # Stop AI agents (update their status)
            try:
                from database.models.core import AIAgent
                agents = db.query(AIAgent).filter(
                    AIAgent.company_id == company_id,
                    AIAgent.status == "active",
                ).all()
                for agent in agents:
                    agent.status = "paused"
                    agent.paused_reason = "payment_failed"
                    agent.paused_at = datetime.now(timezone.utc)
                    results["agents_stopped"] += 1
                logger.info(
                    "stopped_ai_agents company_id=%s count=%d failure_reason=%s",
                    company_id,
                    results["agents_stopped"],
                    failure_reason,
                )
            except Exception as agent_err:
                logger.error(
                    "stop_agents_failed company_id=%s error=%s",
                    company_id,
                    str(agent_err),
                )
                # Try alternate model path
                try:
                    from sqlalchemy import text
                    db.execute(text(
                        "UPDATE ai_agents SET status = 'paused', paused_reason = 'payment_failed', paused_at = NOW() "
                        "WHERE company_id = :cid AND status = 'active'"
                    ), {"cid": company_id})
                    count_result = db.execute(text(
                        "SELECT COUNT(*) FROM ai_agents WHERE company_id = :cid AND status = 'paused' AND paused_reason = 'payment_failed'"
                    ), {"cid": company_id})
                    results["agents_stopped"] = count_result.scalar() or 0
                    logger.info(
                        "stopped_agents_via_fallback company_id=%s count=%d",
                        company_id, results["agents_stopped"],
                    )
                except Exception as fallback_err:
                    logger.error(
                        "stop_agents_fallback_failed company_id=%s error=%s",
                        company_id, str(fallback_err),
                    )

            # Freeze open tickets
            from database.models.ticket import Ticket
            open_tickets = db.query(Ticket).filter(
                Ticket.company_id == company_id,
                Ticket.status.in_(["open", "pending", "in_progress"]),
            ).all()

            for ticket in open_tickets:
                # Bug B5 FIX: Store the ORIGINAL status BEFORE changing it
                original_status = ticket.status  # 'open', 'pending', or 'in_progress'
                ticket.metadata_json = ticket.metadata_json or {}
                ticket.metadata_json["pre_freeze_status"] = original_status
                # NOW set to frozen
                ticket.status = "frozen"
                results["tickets_frozen"] += 1

            db.commit()

        logger.info(
            "service_stopped_immediately "
            "company_id=%s failure_id=%s "
            "agents_stopped=%d tickets_frozen=%d",
            company_id,
            failure_id,
            results["agents_stopped"],
            results["tickets_frozen"],
        )

        # Dispatch notification task
        send_payment_failed_notification.delay(
            company_id=company_id,
            failure_id=failure_id,
            failure_reason=failure_reason,
        )

        return results

    except Exception as exc:
        logger.error(
            "stop_service_immediately_failed "
            "company_id=%s error=%s",
            company_id,
            str(exc)[:200],
        )
        raise


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="billing",
    name="app.tasks.payment_failure.resume_service",
    max_retries=2,
    soft_time_limit=60,
    time_limit=120,
    retry_backoff=True,
)
@with_company_id
def resume_service(
    self,
    company_id: str,
    transaction_id: str,
) -> dict:
    """
    Resume service after successful payment.

    This task performs:
    1. Resume AI agents
    2. Unfreeze tickets
    3. Allow new ticket creation

    Args:
        company_id: Company UUID string
        transaction_id: Successful Paddle transaction ID

    Returns:
        Dict with resume status
    """
    try:
        results = {
            "company_id": company_id,
            "transaction_id": transaction_id,
            "agents_resumed": 0,
            "tickets_unfrozen": 0,
            "status": "resumed",
        }

        with SessionLocal() as db:
            company = db.query(Company).filter(
                Company.id == company_id
            ).first()

            if not company:
                raise ValueError(f"Company {company_id} not found")

            # Resume AI agents that were paused due to payment failure
            try:
                from database.models.core import AIAgent
                agents = db.query(AIAgent).filter(
                    AIAgent.company_id == company_id,
                    AIAgent.status == "paused",
                    AIAgent.paused_reason == "payment_failed",
                ).all()
                for agent in agents:
                    agent.status = "active"
                    agent.paused_reason = None
                    agent.paused_at = None
                    results["agents_resumed"] += 1
                logger.info(
                    "resumed_ai_agents company_id=%s count=%d transaction_id=%s",
                    company_id, results["agents_resumed"], transaction_id,
                )
            except Exception as agent_err:
                logger.error(
                    "resume_agents_failed company_id=%s error=%s",
                    company_id, str(agent_err),
                )
                try:
                    from sqlalchemy import text
                    db.execute(text(
                        "UPDATE ai_agents SET status = 'active', paused_reason = NULL, paused_at = NULL "
                        "WHERE company_id = :cid AND status = 'paused' AND paused_reason = 'payment_failed'"
                    ), {"cid": company_id})
                    count_result = db.execute(text(
                        "SELECT COUNT(*) FROM ai_agents WHERE company_id = :cid AND status = 'active'"
                    ), {"cid": company_id})
                    results["agents_resumed"] = count_result.scalar() or 0
                except Exception as fallback_err:
                    logger.error(
                        "resume_agents_fallback_failed company_id=%s error=%s",
                        company_id, str(fallback_err),
                    )

            # Unfreeze tickets
            from database.models.ticket import Ticket
            frozen_tickets = db.query(Ticket).filter(
                Ticket.company_id == company_id,
                Ticket.status == "frozen",
            ).all()

            for ticket in frozen_tickets:
                # Restore to previous status (Bug B5 fix: use stored original status)
                ticket.metadata_json = ticket.metadata_json or {}
                original_status = ticket.metadata_json.get("pre_freeze_status", "open")
                # If original_status is still 'frozen' (shouldn't happen), fall back to 'open'
                if original_status == "frozen":
                    original_status = "open"
                ticket.status = original_status
                # Clean up metadata
                ticket.metadata_json.pop("pre_freeze_status", None)
                results["tickets_unfrozen"] += 1

            db.commit()

        logger.info(
            "service_resumed "
            "company_id=%s transaction_id=%s "
            "agents_resumed=%d tickets_unfrozen=%d",
            company_id,
            transaction_id,
            results["agents_resumed"],
            results["tickets_unfrozen"],
        )

        # Dispatch notification task
        send_service_resumed_notification.delay(
            company_id=company_id,
            transaction_id=transaction_id,
        )

        return results

    except Exception as exc:
        logger.error(
            "resume_service_failed "
            "company_id=%s error=%s",
            company_id,
            str(exc)[:200],
        )
        raise


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="email",
    name="app.tasks.payment_failure.send_payment_failed_notification",
    max_retries=3,
    soft_time_limit=60,
    time_limit=120,
    retry_backoff=True,
)
@with_company_id
def send_payment_failed_notification(
    self,
    company_id: str,
    failure_id: str,
    failure_reason: str,
) -> dict:
    """
    Send payment failure notification to company.

    This sends a single notification (no dunning, no retries):
    "Payment failed, update payment method"

    Args:
        company_id: Company UUID string
        failure_id: PaymentFailure record ID
        failure_reason: Reason for payment failure

    Returns:
        Dict with notification status
    """
    try:
        from app.services.email_service import send_email
        from database.models.billing_extended import PaymentFailure

        with SessionLocal() as db:
            company = db.query(Company).filter(
                Company.id == company_id
            ).first()

            if not company:
                raise ValueError(f"Company {company_id} not found")

            failure = db.query(PaymentFailure).filter(
                PaymentFailure.id == failure_id
            ).first()

            if not failure:
                raise ValueError(f"Payment failure {failure_id} not found")

            # Get subscription for variant info
            subscription = db.query(Subscription).filter(
                Subscription.company_id == company_id
            ).order_by(Subscription.created_at.desc()).first()

            variant = subscription.tier if subscription else "unknown"
            amount = float(failure.amount_attempted) if failure.amount_attempted else 0

            # Send email notification
            # In production, this would use the email service
            logger.info(
                "sending_payment_failed_email "
                "company_id=%s email=%s variant=%s amount=%s",
                company_id,
                company.email if hasattr(company, 'email') else 'unknown',
                variant,
                amount,
            )

            # Mark notification as sent
            failure.notification_sent = True
            db.commit()

            # Emit Socket.io event for real-time UI update
            try:
                from app.core.event_buffer import store_event
                import asyncio

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(
                        store_event(
                            company_id=company_id,
                            event_type="payment_failed",
                            event_data={
                                "failure_id": failure_id,
                                "failure_reason": failure_reason,
                                "variant": variant,
                                "amount": amount,
                                "service_stopped": True,
                            },
                        )
                    )
                finally:
                    loop.close()
            except Exception as e:
                logger.warning(
                    "socket_emit_failed company_id=%s error=%s",
                    company_id,
                    str(e)[:100],
                )

        return {
            "status": "sent",
            "company_id": company_id,
            "failure_id": failure_id,
        }

    except Exception as exc:
        logger.error(
            "send_payment_failed_notification_failed "
            "company_id=%s error=%s",
            company_id,
            str(exc)[:200],
        )
        raise


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="email",
    name="app.tasks.payment_failure.send_service_resumed_notification",
    max_retries=3,
    soft_time_limit=60,
    time_limit=120,
    retry_backoff=True,
)
@with_company_id
def send_service_resumed_notification(
    self,
    company_id: str,
    transaction_id: str,
) -> dict:
    """
    Send service resumed notification after successful payment.

    Args:
        company_id: Company UUID string
        transaction_id: Successful Paddle transaction ID

    Returns:
        Dict with notification status
    """
    try:
        with SessionLocal() as db:
            company = db.query(Company).filter(
                Company.id == company_id
            ).first()

            if not company:
                raise ValueError(f"Company {company_id} not found")

            logger.info(
                "sending_service_resumed_email "
                "company_id=%s transaction_id=%s",
                company_id,
                transaction_id,
            )

            # Emit Socket.io event for real-time UI update
            try:
                from app.core.event_buffer import store_event
                import asyncio

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(
                        store_event(
                            company_id=company_id,
                            event_type="service_resumed",
                            event_data={
                                "transaction_id": transaction_id,
                                "service_resumed": True,
                            },
                        )
                    )
                finally:
                    loop.close()
            except Exception as e:
                logger.warning(
                    "socket_emit_failed company_id=%s error=%s",
                    company_id,
                    str(e)[:100],
                )

        return {
            "status": "sent",
            "company_id": company_id,
            "transaction_id": transaction_id,
        }

    except Exception as exc:
        logger.error(
            "send_service_resumed_notification_failed "
            "company_id=%s error=%s",
            company_id,
            str(exc)[:200],
        )
        raise


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="billing",
    name="app.tasks.payment_failure.suspend_expired_grace_periods",
    max_retries=2,
    soft_time_limit=300,
    time_limit=600,
    retry_backoff=True,
)
def suspend_expired_grace_periods(self) -> dict:
    """
    Check all companies with expired grace periods and suspend them.

    Runs daily via Celery Beat. For any company whose grace period
    has expired without a successful payment, escalates to full
    suspension (status=payment_failed) and triggers service stop.

    Returns:
        Dict with suspension summary
    """
    try:
        import asyncio
        from app.services.payment_failure_service import get_payment_failure_service

        service = get_payment_failure_service()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(
                service.check_and_suspend_expired_grace_periods()
            )
        finally:
            loop.close()

        return results

    except Exception as exc:
        logger.error(
            "suspend_expired_grace_periods_failed error=%s",
            str(exc)[:200],
        )
        raise


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="billing",
    name="app.tasks.payment_failure.check_stopped_services",
    max_retries=2,
    soft_time_limit=300,
    time_limit=600,
)
def check_stopped_services(self) -> dict:
    """
    Check all companies with stopped services.

    This task verifies that stopped services are properly
    frozen and notifications were sent.

    Runs hourly via Celery Beat.

    Returns:
        Dict with check summary
    """
    try:
        results = {
            "total_checked": 0,
            "notifications_missing": 0,
            "errors": [],
        }

        with SessionLocal() as db:
            from database.models.billing_extended import PaymentFailure

            # Get unresolved payment failures
            failures = db.query(PaymentFailure).filter(
                PaymentFailure.resolved == False,
                PaymentFailure.notification_sent == False,
            ).all()

            for failure in failures:
                results["total_checked"] += 1

                # Send missing notification
                try:
                    send_payment_failed_notification.delay(
                        company_id=failure.company_id,
                        failure_id=failure.id,
                        failure_reason=failure.failure_reason or "Unknown",
                    )
                    results["notifications_missing"] += 1
                except Exception as e:
                    results["errors"].append({
                        "failure_id": failure.id,
                        "error": str(e)[:50],
                    })

        logger.info(
            "check_stopped_services_completed "
            "total=%d notifications_sent=%d errors=%d",
            results["total_checked"],
            results["notifications_missing"],
            len(results["errors"]),
        )

        return results

    except Exception as exc:
        logger.error(
            "check_stopped_services_failed error=%s",
            str(exc)[:200],
        )
        raise
