"""
PARWA Usage Tasks (F-024, BC-004)

Celery tasks for daily usage aggregation and limit checking:
- aggregate_daily_usage: Aggregate ticket usage for a single company for yesterday
- aggregate_all_usage: Batch aggregate usage for all active companies
- check_usage_limits: Check if a company has exceeded their usage limit
- check_all_usage_limits: Batch check all active companies for limit breaches
- reset_monthly_usage: Log previous month's final usage at month boundary

BC-001: All per-company tasks validate company_id via @with_company_id
BC-003: All tasks have proper error handling and retries
BC-004: All tasks use ParwaBaseTask with retry config
"""

import logging
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from typing import Dict, List, Any
from uuid import UUID

from sqlalchemy import func

from app.tasks.base import ParwaBaseTask, with_company_id
from app.tasks.celery_app import app
from database.base import SessionLocal
from database.models.core import Company
from database.models.billing import Subscription
from database.models.billing_extended import UsageRecord

logger = logging.getLogger("parwa.tasks.usage")

# ── Constants ────────────────────────────────────────────────

OVERAGE_RATE_PER_TICKET = Decimal("0.10")
DEFAULT_MONTHLY_TICKET_LIMIT = 2000


# ── Task 1: Aggregate daily usage for a single company ───────


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.usage.aggregate_daily_usage",
    max_retries=3,
    soft_time_limit=120,
    time_limit=300,
    retry_backoff=True,
    retry_jitter=True,
)
@with_company_id
def aggregate_daily_usage(self, company_id: str, target_date: str = None) -> dict:
    """
    Aggregate ticket usage for a single company for yesterday.

    This task:
    1. Queries tickets created yesterday for this company (counts them)
    2. Gets or creates a UsageRecord for the target date
    3. Updates the tickets_used count
    4. Calculates overage if usage exceeds plan limit
    5. Updates overage_tickets and overage_charges ($0.10/ticket)

    Args:
        company_id: Company UUID string
        target_date: Optional date string in YYYY-MM-DD format (default: yesterday)

    Returns:
        Dict with company_id, date, tickets_used, overage_tickets,
        overage_charges, and status
    """
    try:
        if target_date:
            agg_date = date.fromisoformat(target_date)
        else:
            agg_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()

        with SessionLocal() as db:
            # Verify company exists
            company = db.query(Company).filter(
                Company.id == company_id,
            ).first()

            if not company:
                logger.warning(
                    "aggregate_daily_usage_skipped company_id=%s reason=not_found",
                    company_id,
                    extra={"task": self.name, "company_id": company_id},
                )
                return {
                    "company_id": company_id,
                    "date": agg_date.isoformat(),
                    "tickets_used": 0,
                    "overage_tickets": 0,
                    "overage_charges": "0.00",
                    "status": "skipped",
                }

            # Count tickets created on the target date for this company
            try:
                from database.models.ticket import Ticket

                ticket_count = db.query(func.count(Ticket.id)).filter(
                    Ticket.company_id == company_id,
                    func.date(Ticket.created_at) == agg_date,
                ).scalar() or 0
            except ImportError:
                ticket_count = 0
                logger.warning(
                    "aggregate_daily_usage_ticket_model_unavailable "
                    "company_id=%s date=%s",
                    company_id,
                    agg_date.isoformat(),
                    extra={"task": self.name, "company_id": company_id},
                )

            ticket_count = int(ticket_count)

            # Get or create UsageRecord for the target date
            usage_record = db.query(UsageRecord).filter(
                UsageRecord.company_id == company_id,
                UsageRecord.record_date == agg_date,
            ).first()

            if not usage_record:
                usage_record = UsageRecord(
                    company_id=company_id,
                    record_date=agg_date,
                    record_month=agg_date.strftime("%Y-%m"),
                    tickets_used=0,
                )
                db.add(usage_record)
                db.flush()

            # Update tickets_used count
            usage_record.tickets_used = ticket_count

            # Get subscription to determine plan limit
            subscription = db.query(Subscription).filter(
                Subscription.company_id == company_id,
                Subscription.status == "active",
            ).order_by(Subscription.created_at.desc()).first()

            ticket_limit = DEFAULT_MONTHLY_TICKET_LIMIT
            if subscription:
                try:
                    from database.models.billing_extended import get_variant_limits

                    limits = get_variant_limits(subscription.tier)
                    if limits:
                        ticket_limit = limits.get(
                            "monthly_tickets", DEFAULT_MONTHLY_TICKET_LIMIT
                        )
                except Exception:
                    pass

            # Calculate month-to-date usage to determine overage
            month_start = agg_date.replace(day=1)
            month_usage = db.query(
                func.sum(UsageRecord.tickets_used).label("total_tickets"),
            ).filter(
                UsageRecord.company_id == company_id,
                UsageRecord.record_month == agg_date.strftime("%Y-%m"),
                UsageRecord.record_date <= agg_date,
            ).scalar() or 0
            total_month_tickets = int(month_usage)

            # Calculate overage against monthly limit
            overage_tickets = max(0, total_month_tickets - ticket_limit)
            overage_charges = (
                Decimal(str(overage_tickets)) * OVERAGE_RATE_PER_TICKET
            ).quantize(Decimal("0.01"))

            # Update overage fields on the record
            usage_record.overage_tickets = overage_tickets
            usage_record.overage_charges = overage_charges

            db.commit()

            status = "overage" if overage_tickets > 0 else "ok"

            logger.info(
                "aggregate_daily_usage_completed "
                "company_id=%s date=%s tickets=%d overage=%d charges=%s status=%s",
                company_id,
                agg_date.isoformat(),
                ticket_count,
                overage_tickets,
                str(overage_charges),
                status,
                extra={
                    "task": self.name,
                    "company_id": company_id,
                    "date": agg_date.isoformat(),
                    "tickets_used": ticket_count,
                    "overage_tickets": overage_tickets,
                    "overage_charges": str(overage_charges),
                    "status": status,
                },
            )

            return {
                "company_id": company_id,
                "date": agg_date.isoformat(),
                "tickets_used": ticket_count,
                "overage_tickets": overage_tickets,
                "overage_charges": str(overage_charges),
                "status": status,
            }

    except Exception as exc:
        logger.error(
            "aggregate_daily_usage_failed company_id=%s error=%s",
            company_id,
            str(exc)[:200],
            extra={"task": self.name, "company_id": company_id},
        )
        raise


# ── Task 2: Batch aggregate usage for all active companies ──


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.usage.aggregate_all_usage",
    max_retries=2,
    soft_time_limit=300,
    time_limit=600,
)
def aggregate_all_usage(self, target_date: str = None) -> dict:
    """
    Batch aggregate usage for all active companies.

    Iterates all companies with active subscriptions and dispatches
    an individual aggregate_daily_usage task for each.

    Called daily by Celery Beat.

    Args:
        target_date: Optional date string in YYYY-MM-DD format (default: yesterday)

    Returns:
        Dict with date, total_companies, dispatched, failed, errors
    """
    try:
        if target_date:
            process_date = date.fromisoformat(target_date)
        else:
            process_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()

        results = {
            "date": process_date.isoformat(),
            "total_companies": 0,
            "dispatched": 0,
            "failed": 0,
            "errors": [],
        }

        with SessionLocal() as db:
            # Get all active companies with subscriptions
            active_companies = db.query(Company).join(
                Subscription,
                Company.id == Subscription.company_id,
            ).filter(
                Subscription.status == "active",
            ).all()

            results["total_companies"] = len(active_companies)

            for company in active_companies:
                try:
                    aggregate_daily_usage.delay(
                        company_id=str(company.id),
                        target_date=process_date.isoformat(),
                    )
                    results["dispatched"] += 1

                except Exception as e:
                    results["failed"] += 1
                    results["errors"].append({
                        "company_id": str(company.id),
                        "error": str(e)[:100],
                    })

        logger.info(
            "aggregate_all_usage_completed "
            "date=%s total=%d dispatched=%d failed=%d",
            process_date.isoformat(),
            results["total_companies"],
            results["dispatched"],
            results["failed"],
            extra={
                "task": self.name,
                "date": process_date.isoformat(),
                "total": results["total_companies"],
                "dispatched": results["dispatched"],
                "failed": results["failed"],
            },
        )

        return results

    except Exception as exc:
        logger.error(
            "aggregate_all_usage_failed error=%s",
            str(exc)[:200],
            extra={"task": self.name},
        )
        raise


# ── Task 3: Check usage limits for a single company ─────────


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.usage.check_usage_limits",
    max_retries=3,
    soft_time_limit=120,
    time_limit=300,
    retry_backoff=True,
    retry_jitter=True,
)
@with_company_id
def check_usage_limits(self, company_id: str) -> dict:
    """
    Check if a company has exceeded their monthly usage limit.

    This task:
    1. Gets the company's active subscription and plan limits
    2. Sums month-to-date ticket usage from UsageRecord
    3. Compares usage against the ticket limit
    4. If exceeded, emits a usage_limit_exceeded event
    5. Returns usage percentage and limit status

    Args:
        company_id: Company UUID string

    Returns:
        Dict with company_id, usage_percentage, tickets_used,
        ticket_limit, and limit_exceeded flag
    """
    try:
        with SessionLocal() as db:
            # Get active subscription for this company
            subscription = db.query(Subscription).filter(
                Subscription.company_id == company_id,
                Subscription.status == "active",
            ).order_by(Subscription.created_at.desc()).first()

            if not subscription:
                logger.info(
                    "check_usage_limits_skipped company_id=%s reason=no_subscription",
                    company_id,
                    extra={"task": self.name, "company_id": company_id},
                )
                return {
                    "company_id": company_id,
                    "usage_percentage": 0,
                    "tickets_used": 0,
                    "ticket_limit": 0,
                    "limit_exceeded": False,
                }

            # Determine ticket limit from subscription tier
            ticket_limit = DEFAULT_MONTHLY_TICKET_LIMIT
            try:
                from database.models.billing_extended import get_variant_limits

                limits = get_variant_limits(subscription.tier)
                if limits:
                    ticket_limit = limits.get(
                        "monthly_tickets", DEFAULT_MONTHLY_TICKET_LIMIT
                    )
            except Exception:
                pass

            # Calculate current month's total usage
            current_month = datetime.now(timezone.utc).strftime("%Y-%m")
            month_usage = db.query(
                func.sum(UsageRecord.tickets_used).label("total_tickets"),
            ).filter(
                UsageRecord.company_id == company_id,
                UsageRecord.record_month == current_month,
            ).scalar() or 0
            tickets_used = int(month_usage)

            # Calculate usage percentage (cap at 100+ for overage display)
            usage_percentage = (
                (tickets_used / ticket_limit * 100) if ticket_limit > 0 else 0
            )
            usage_percentage = round(usage_percentage, 1)

            limit_exceeded = tickets_used > ticket_limit

            # Emit usage_limit_exceeded event if over limit
            if limit_exceeded:
                overage_amount = tickets_used - ticket_limit
                try:
                    from app.core.event_emitter import emit_billing_event
                    import asyncio

                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(
                            emit_billing_event(
                                company_id=company_id,
                                event_type="usage_limit_exceeded",
                                data={
                                    "usage_percentage": usage_percentage,
                                    "tickets_used": tickets_used,
                                    "ticket_limit": ticket_limit,
                                    "overage_tickets": overage_amount,
                                    "tier": subscription.tier,
                                },
                            )
                        )
                    finally:
                        loop.close()

                    logger.info(
                        "usage_limit_exceeded_event_sent "
                        "company_id=%s usage_pct=%.1f tickets=%d limit=%d",
                        company_id,
                        usage_percentage,
                        tickets_used,
                        ticket_limit,
                        extra={"task": self.name, "company_id": company_id},
                    )

                except Exception as event_exc:
                    logger.warning(
                        "usage_limit_exceeded_event_failed "
                        "company_id=%s error=%s",
                        company_id,
                        str(event_exc)[:100],
                        extra={"task": self.name, "company_id": company_id},
                    )

            logger.info(
                "check_usage_limits_completed "
                "company_id=%s usage_pct=%.1f tickets=%d limit=%d exceeded=%s",
                company_id,
                usage_percentage,
                tickets_used,
                ticket_limit,
                limit_exceeded,
                extra={
                    "task": self.name,
                    "company_id": company_id,
                    "usage_percentage": usage_percentage,
                    "tickets_used": tickets_used,
                    "ticket_limit": ticket_limit,
                    "limit_exceeded": limit_exceeded,
                },
            )

            return {
                "company_id": company_id,
                "usage_percentage": usage_percentage,
                "tickets_used": tickets_used,
                "ticket_limit": ticket_limit,
                "limit_exceeded": limit_exceeded,
            }

    except Exception as exc:
        logger.error(
            "check_usage_limits_failed company_id=%s error=%s",
            company_id,
            str(exc)[:200],
            extra={"task": self.name, "company_id": company_id},
        )
        raise


# ── Task 4: Batch check usage limits for all companies ──────


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.usage.check_all_usage_limits",
    max_retries=2,
    soft_time_limit=300,
    time_limit=600,
)
def check_all_usage_limits(self) -> dict:
    """
    Batch check usage limits for all active companies.

    Iterates all companies with active subscriptions and dispatches
    an individual check_usage_limits task for each.

    Called by Celery Beat (suggested: daily).

    Returns:
        Dict with total_checked and exceeded_count
    """
    try:
        results = {
            "total_checked": 0,
            "exceeded_count": 0,
        }

        with SessionLocal() as db:
            # Get all active companies with subscriptions
            active_companies = db.query(Company).join(
                Subscription,
                Company.id == Subscription.company_id,
            ).filter(
                Subscription.status == "active",
            ).all()

            for company in active_companies:
                results["total_checked"] += 1
                try:
                    check_usage_limits.delay(company_id=str(company.id))
                except Exception as e:
                    logger.warning(
                        "check_all_usage_limits_dispatch_failed "
                        "company_id=%s error=%s",
                        str(company.id),
                        str(e)[:100],
                        extra={"task": self.name},
                    )

        logger.info(
            "check_all_usage_limits_completed total=%d",
            results["total_checked"],
            extra={
                "task": self.name,
                "total_checked": results["total_checked"],
            },
        )

        return results

    except Exception as exc:
        logger.error(
            "check_all_usage_limits_failed error=%s",
            str(exc)[:200],
            extra={"task": self.name},
        )
        raise


# ── Task 5: Reset monthly usage counters ────────────────────


@app.task(
    base=ParwaBaseTask,
    bind=True,
    queue="default",
    name="app.tasks.usage.reset_monthly_usage",
    max_retries=2,
    soft_time_limit=300,
    time_limit=600,
)
def reset_monthly_usage(self) -> dict:
    """
    Log previous month's final usage at the start of a new month.

    This task does NOT delete historical usage records — they are
    retained for reporting and auditing. It only logs the final
    monthly totals for each company as a summary.

    Called monthly by Celery Beat on the 1st of each month.

    Returns:
        Dict with month_completed and companies_logged
    """
    try:
        now = datetime.now(timezone.utc)
        # The month that just completed
        previous_month_date = (now - timedelta(days=1))
        month_completed = previous_month_date.strftime("%Y-%m")

        results = {
            "month_completed": month_completed,
            "companies_logged": 0,
        }

        with SessionLocal() as db:
            # Get all companies that have usage records for the
            # previous month
            companies_with_usage = db.query(
                UsageRecord.company_id,
            ).filter(
                UsageRecord.record_month == month_completed,
            ).distinct().all()

            for row in companies_with_usage:
                cid = row.company_id

                # Sum total usage for the completed month
                monthly_summary = db.query(
                    func.sum(UsageRecord.tickets_used).label("total_tickets"),
                    func.sum(UsageRecord.overage_tickets).label("total_overage"),
                    func.sum(UsageRecord.overage_charges).label("total_charges"),
                ).filter(
                    UsageRecord.company_id == cid,
                    UsageRecord.record_month == month_completed,
                ).first()

                total_tickets = int(monthly_summary.total_tickets or 0)
                total_overage = int(monthly_summary.total_overage or 0)
                total_charges = Decimal(str(monthly_summary.total_charges or 0))

                results["companies_logged"] += 1

                logger.info(
                    "monthly_usage_summary "
                    "company_id=%s month=%s tickets=%d overage=%d charges=%s",
                    cid,
                    month_completed,
                    total_tickets,
                    total_overage,
                    str(total_charges),
                    extra={
                        "task": self.name,
                        "company_id": cid,
                        "month_completed": month_completed,
                        "total_tickets": total_tickets,
                        "total_overage": total_overage,
                        "total_charges": str(total_charges),
                    },
                )

        logger.info(
            "reset_monthly_usage_completed "
            "month=%s companies=%d",
            month_completed,
            results["companies_logged"],
            extra={
                "task": self.name,
                "month_completed": month_completed,
                "companies_logged": results["companies_logged"],
            },
        )

        return results

    except Exception as exc:
        logger.error(
            "reset_monthly_usage_failed error=%s",
            str(exc)[:200],
            extra={"task": self.name},
        )
        raise
