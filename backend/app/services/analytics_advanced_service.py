"""
PARWA Analytics Advanced Services (Week 15 — Dashboard + Analytics)

Services for advanced analytics features:
- F-039: Adaptation Tracker — 30-day AI learning progress
- F-040: Running Savings Counter — AI vs human cost comparison
- F-041: Workforce Allocation — AI vs human distribution

Building Codes: BC-001 (multi-tenant), BC-002 (financial),
               BC-007 (AI model), BC-012 (error handling)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.logger import get_logger
from database.models.tickets import (
    Ticket,
    TicketFeedback,
    TicketStatus,
    TicketAssignment,
)

logger = get_logger("analytics_advanced_service")

# ══════════════════════════════════════════════════════════════════
# DEFAULTS
# ══════════════════════════════════════════════════════════════════

# Default cost estimates (BC-002)
DEFAULT_AI_COST_PER_TICKET = 0.15  # $0.15
DEFAULT_HUMAN_COST_PER_TICKET = 8.00  # $8.00

# Adaptation tracker defaults
ADAPTATION_DAYS = 30


# ═════════════════-hand═══════════════════════════════════════════
# F-039: ADAPTATION TRACKER — 30-Day AI Learning Progress
# ══════════════════════════════════════════════════════════════════


def get_adaptation_tracker(
    company_id: str,
    db: Session,
    days: int = ADAPTATION_DAYS,
) -> Dict[str, Any]:
    """Get 30-day AI adaptation/learning progress.

    Tracks AI accuracy improvement over time by comparing
    AI-resolved tickets' CSAT scores vs human-resolved tickets.
    Includes mistake rates, training runs, and drift reports.

    F-039: Adaptation Tracker
    BC-001: Scoped by company_id.
    BC-007: AI model learning metrics.
    """
    try:
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days)

        daily_data: List[Dict[str, Any]] = []
        ai_ratings: List[float] = []
        human_ratings: List[float] = []

        for i in range(days):
            day_start = start + timedelta(days=i)
            day_end = day_start + timedelta(days=1)

            day_data = _get_adaptation_day(
                db,
                company_id,
                day_start,
                day_end,
            )
            day_data["date"] = day_start.strftime("%Y-%m-%d")
            daily_data.append(day_data)

            if day_data["ai_accuracy"] > 0:
                ai_ratings.append(day_data["ai_accuracy"])
            if day_data["human_accuracy"] > 0:
                human_ratings.append(day_data["human_accuracy"])

        # Calculate overall improvement
        current_accuracy = ai_ratings[-1] if ai_ratings else 0
        starting_accuracy = ai_ratings[0] if ai_ratings else 0
        overall_improvement = 0.0
        if starting_accuracy > 0 and current_accuracy > 0:
            overall_improvement = round(
                ((current_accuracy - starting_accuracy) / starting_accuracy) * 100,
                1,
            )

        # Best and worst days
        best_day = None
        worst_day = None
        if daily_data:
            valid_days = [d for d in daily_data if d["ai_accuracy"] > 0]
            if valid_days:
                best_day = max(valid_days, key=lambda d: d["ai_accuracy"])
                worst_day = min(valid_days, key=lambda d: d["ai_accuracy"])

        # Training runs and drift reports count
        training_count = _count_training_runs(db, company_id, start, now)
        drift_count = _count_drift_reports(db, company_id, start, now)

        return {
            "daily_data": daily_data,
            "overall_improvement_pct": overall_improvement,
            "current_accuracy": round(current_accuracy, 2),
            "starting_accuracy": round(starting_accuracy, 2),
            "best_day": best_day,
            "worst_day": worst_day,
            "training_runs_count": training_count,
            "drift_reports_count": drift_count,
        }

    except Exception as exc:
        logger.error(
            "adaptation_tracker_error",
            company_id=company_id,
            error=str(exc),
        )
        return {
            "daily_data": [],
            "overall_improvement_pct": 0,
            "current_accuracy": 0,
            "starting_accuracy": 0,
            "best_day": None,
            "worst_day": None,
            "training_runs_count": 0,
            "drift_reports_count": 0,
        }


def _get_adaptation_day(
    db: Session,
    company_id: str,
    day_start: datetime,
    day_end: datetime,
) -> Dict[str, Any]:
    """Get single day's adaptation data."""
    # AI accuracy: average CSAT for AI-resolved tickets
    ai_accuracy = 0.0
    ai_tickets = 0
    ai_mistakes = 0

    # Get AI-resolved ticket CSAT scores
    ai_csat = (
        db.query(func.avg(TicketFeedback.rating))
        .join(
            Ticket,
            Ticket.id == TicketFeedback.ticket_id,
        )
        .join(
            TicketAssignment,
            and_(
                TicketAssignment.ticket_id == Ticket.id,
                TicketAssignment.assignee_type == "ai",
            ),
        )
        .filter(
            Ticket.company_id == company_id,
            TicketFeedback.created_at >= day_start,
            TicketFeedback.created_at < day_end,
        )
        .scalar()
    )

    if ai_csat is not None:
        ai_accuracy = round(float(ai_csat), 2)

    # AI ticket count
    ai_tickets = (
        db.query(func.count(TicketAssignment.id))
        .filter(
            TicketAssignment.company_id == company_id,
            TicketAssignment.assigned_at >= day_start,
            TicketAssignment.assigned_at < day_end,
            TicketAssignment.assignee_type == "ai",
        )
        .scalar()
        or 0
    )

    # AI mistakes: low CSAT (1-2 stars) from AI
    ai_mistakes = (
        db.query(func.count(TicketFeedback.id))
        .join(
            Ticket,
            Ticket.id == TicketFeedback.ticket_id,
        )
        .join(
            TicketAssignment,
            and_(
                TicketAssignment.ticket_id == Ticket.id,
                TicketAssignment.assignee_type == "ai",
            ),
        )
        .filter(
            Ticket.company_id == company_id,
            TicketFeedback.created_at >= day_start,
            TicketFeedback.created_at < day_end,
            TicketFeedback.rating <= 2,
        )
        .scalar()
        or 0
    )

    # Human accuracy: average CSAT for human-resolved tickets
    human_accuracy = 0.0
    human_csat = (
        db.query(func.avg(TicketFeedback.rating))
        .join(
            Ticket,
            Ticket.id == TicketFeedback.ticket_id,
        )
        .join(
            TicketAssignment,
            and_(
                TicketAssignment.ticket_id == Ticket.id,
                TicketAssignment.assignee_type == "human",
            ),
        )
        .filter(
            Ticket.company_id == company_id,
            TicketFeedback.created_at >= day_start,
            TicketFeedback.created_at < day_end,
        )
        .scalar()
    )

    if human_csat is not None:
        human_accuracy = round(float(human_csat), 2)

    mistake_rate = 0.0
    if ai_tickets > 0:
        mistake_rate = round((ai_mistakes / ai_tickets) * 100, 1)

    return {
        "ai_accuracy": ai_accuracy,
        "human_accuracy": human_accuracy,
        "gap": round(ai_accuracy - human_accuracy, 2),
        "tickets_processed": ai_tickets,
        "mistakes_count": ai_mistakes,
        "mistake_rate": mistake_rate,
    }


def _count_training_runs(
    db: Session,
    company_id: str,
    start: datetime,
    end: datetime,
) -> int:
    """Count training runs in date range."""
    try:
        from database.models.analytics import TrainingRun

        return (
            db.query(func.count(TrainingRun.id))
            .filter(
                TrainingRun.company_id == company_id,
                TrainingRun.created_at >= start,
                TrainingRun.created_at <= end,
            )
            .scalar()
            or 0
        )
    except Exception:
        return 0


def _count_drift_reports(
    db: Session,
    company_id: str,
    start: datetime,
    end: datetime,
) -> int:
    """Count drift reports in date range."""
    try:
        from database.models.analytics import DriftReport

        return (
            db.query(func.count(DriftReport.id))
            .filter(
                DriftReport.company_id == company_id,
                DriftReport.created_at >= start,
                DriftReport.created_at <= end,
            )
            .scalar()
            or 0
        )
    except Exception:
        return 0


# ══════════════════════════════════════════════════════════════════
# F-040: RUNNING SAVINGS COUNTER — AI vs Human Cost
# ══════════════════════════════════════════════════════════════════


def get_savings_counter(
    company_id: str,
    db: Session,
    months: int = 12,
) -> Dict[str, Any]:
    """Get running savings counter — AI vs human cost comparison.

    Calculates cumulative savings from AI-resolved tickets vs
    what they would have cost with human agents.

    F-040: Running Savings Counter
    BC-001: Scoped by company_id.
    BC-002: Financial metrics use proper precision.
    """
    try:
        now = datetime.now(timezone.utc)
        monthly_trend: List[Dict[str, Any]] = []
        all_time_ai = 0
        all_time_human = 0
        all_time_savings = 0.0

        for i in range(months):
            month_start = (now.replace(day=1) - timedelta(days=30 * i)).replace(
                day=1,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            # Calculate next month start
            if month_start.month == 12:
                month_end = month_start.replace(year=month_start.year + 1, month=1)
            else:
                month_end = month_start.replace(month=month_start.month + 1)

            snapshot = _get_monthly_savings(
                db,
                company_id,
                month_start,
                month_end,
            )

            cumulative = all_time_savings + snapshot["savings"]
            snapshot["cumulative_savings"] = round(cumulative, 2)
            snapshot["period"] = month_start.strftime("%Y-%m")
            snapshot["date"] = month_start.strftime("%Y-%m-%d")

            monthly_trend.append(snapshot)
            all_time_ai += snapshot["tickets_ai"]
            all_time_human += snapshot["tickets_human"]
            all_time_savings = cumulative

        # Current and previous month
        current_month = monthly_trend[0] if monthly_trend else _empty_snapshot()
        previous_month = (
            monthly_trend[1] if len(monthly_trend) > 1 else _empty_snapshot()
        )

        # Calculate averages
        total_ai = max(all_time_ai, 1)
        total_human = max(all_time_human, 1)
        avg_ai_cost = _get_avg_ai_cost(db, company_id, now - timedelta(days=30), now)
        avg_human_cost = _get_avg_human_cost(
            db, company_id, now - timedelta(days=30), now
        )

        savings_pct = 0.0
        if avg_human_cost > 0:
            savings_pct = round(
                ((avg_human_cost - avg_ai_cost) / avg_human_cost) * 100,
                1,
            )

        return {
            "current_month": current_month,
            "previous_month": previous_month,
            "all_time_savings": round(all_time_savings, 2),
            "all_time_tickets_ai": all_time_ai,
            "all_time_tickets_human": all_time_human,
            "monthly_trend": monthly_trend,
            "avg_cost_per_ticket_ai": round(avg_ai_cost, 2),
            "avg_cost_per_ticket_human": round(avg_human_cost, 2),
            "savings_pct": savings_pct,
        }

    except Exception as exc:
        logger.error(
            "savings_counter_error",
            company_id=company_id,
            error=str(exc),
        )
        return _empty_savings_response()


def _get_monthly_savings(
    db: Session,
    company_id: str,
    month_start: datetime,
    month_end: datetime,
) -> Dict[str, Any]:
    """Get savings data for a single month."""
    # AI-resolved tickets
    ai_tickets = (
        db.query(func.count(TicketAssignment.id))
        .filter(
            TicketAssignment.company_id == company_id,
            TicketAssignment.assigned_at >= month_start,
            TicketAssignment.assigned_at < month_end,
            TicketAssignment.assignee_type == "ai",
        )
        .scalar()
        or 0
    )

    # Human-resolved tickets
    human_tickets = (
        db.query(func.count(TicketAssignment.id))
        .filter(
            TicketAssignment.company_id == company_id,
            TicketAssignment.assigned_at >= month_start,
            TicketAssignment.assigned_at < month_end,
            TicketAssignment.assignee_type == "human",
        )
        .scalar()
        or 0
    )

    ai_cost = round(
        ai_tickets * _get_avg_ai_cost(db, company_id, month_start, month_end), 2
    )
    human_cost = round(
        human_tickets * _get_avg_human_cost(db, company_id, month_start, month_end), 2
    )
    savings = round(human_cost - ai_cost, 2)

    return {
        "tickets_ai": ai_tickets,
        "tickets_human": human_tickets,
        "ai_cost": ai_cost,
        "human_cost": human_cost,
        "savings": savings,
        "cumulative_savings": savings,
    }


def _get_avg_ai_cost(
    db: Session,
    company_id: str,
    start: datetime,
    end: datetime,
) -> float:
    """Get average cost per AI-resolved ticket.

    Uses ROISnapshot if available, else default estimate.
    """
    try:
        from database.models.analytics import ROISnapshot

        snapshot = (
            db.query(ROISnapshot)
            .filter(
                ROISnapshot.company_id == company_id,
                ROISnapshot.snapshot_date >= start,
                ROISnapshot.snapshot_date <= end,
            )
            .first()
        )
        if snapshot and snapshot.avg_ai_cost:
            return float(snapshot.avg_ai_cost)
    except Exception:
        pass
    return DEFAULT_AI_COST_PER_TICKET


def _get_avg_human_cost(
    db: Session,
    company_id: str,
    start: datetime,
    end: datetime,
) -> float:
    """Get average cost per human-resolved ticket."""
    try:
        from database.models.analytics import ROISnapshot

        snapshot = (
            db.query(ROISnapshot)
            .filter(
                ROISnapshot.company_id == company_id,
                ROISnapshot.snapshot_date >= start,
                ROISnapshot.snapshot_date <= end,
            )
            .first()
        )
        if snapshot and snapshot.avg_human_cost:
            return float(snapshot.avg_human_cost)
    except Exception:
        pass
    return DEFAULT_HUMAN_COST_PER_TICKET


def _empty_snapshot() -> Dict[str, Any]:
    """Return an empty savings snapshot."""
    return {
        "tickets_ai": 0,
        "tickets_human": 0,
        "ai_cost": 0.0,
        "human_cost": 0.0,
        "savings": 0.0,
        "cumulative_savings": 0.0,
        "period": "",
        "date": "",
    }


def _empty_savings_response() -> Dict[str, Any]:
    """Return an empty savings response."""
    return {
        "current_month": _empty_snapshot(),
        "previous_month": _empty_snapshot(),
        "all_time_savings": 0.0,
        "all_time_tickets_ai": 0,
        "all_time_tickets_human": 0,
        "monthly_trend": [],
        "avg_cost_per_ticket_ai": DEFAULT_AI_COST_PER_TICKET,
        "avg_cost_per_ticket_human": DEFAULT_HUMAN_COST_PER_TICKET,
        "savings_pct": 0.0,
    }


# ══════════════════════════════════════════════════════════════════
# F-041: WORKFORCE ALLOCATION — AI vs Human Distribution
# ══════════════════════════════════════════════════════════════════


def get_workforce_allocation(
    company_id: str,
    db: Session,
    days: int = 30,
) -> Dict[str, Any]:
    """Get AI vs human workforce allocation distribution.

    Shows ticket distribution between AI and human agents over time,
    broken down by channel and category.

    F-041: Workforce Allocation
    BC-001: Scoped by company_id.
    """
    try:
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days)

        # Daily trend
        daily_trend = []
        for i in range(days):
            day_start = start + timedelta(days=i)
            day_end = day_start + timedelta(days=1)
            split = _get_daily_split(db, company_id, day_start, day_end)
            split["date"] = day_start.strftime("%Y-%m-%d")
            daily_trend.append(split)

        # Current split (today + last 30 days combined)
        current_split = _get_daily_split(db, company_id, start, now)
        current_split["date"] = now.strftime("%Y-%m-%d")

        # By channel
        by_channel = _get_channel_split(db, company_id, start, now)

        # By category
        by_category = _get_category_split(db, company_id, start, now)

        # Resolution rates
        ai_resolution = _get_resolution_rate_by_type(db, company_id, start, now, "ai")
        human_resolution = _get_resolution_rate_by_type(
            db, company_id, start, now, "human"
        )

        return {
            "current_split": current_split,
            "daily_trend": daily_trend,
            "by_channel": by_channel,
            "by_category": by_category,
            "ai_resolution_rate": round(ai_resolution, 1),
            "human_resolution_rate": round(human_resolution, 1),
        }

    except Exception as exc:
        logger.error(
            "workforce_allocation_error",
            company_id=company_id,
            error=str(exc),
        )
        return _empty_workforce_response()


def _get_daily_split(
    db: Session,
    company_id: str,
    start: datetime,
    end: datetime,
) -> Dict[str, Any]:
    """Get AI vs human split for a time period."""
    ai_count = (
        db.query(func.count(TicketAssignment.id))
        .filter(
            TicketAssignment.company_id == company_id,
            TicketAssignment.assigned_at >= start,
            TicketAssignment.assigned_at < end,
            TicketAssignment.assignee_type == "ai",
        )
        .scalar()
        or 0
    )

    human_count = (
        db.query(func.count(TicketAssignment.id))
        .filter(
            TicketAssignment.company_id == company_id,
            TicketAssignment.assigned_at >= start,
            TicketAssignment.assigned_at < end,
            TicketAssignment.assignee_type == "human",
        )
        .scalar()
        or 0
    )

    total = ai_count + human_count
    return {
        "period": f"{start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}",
        "ai_tickets": ai_count,
        "human_tickets": human_count,
        "ai_pct": round((ai_count / total * 100), 1) if total > 0 else 0,
        "human_pct": round((human_count / total * 100), 1) if total > 0 else 0,
        "total": total,
    }


def _get_channel_split(
    db: Session,
    company_id: str,
    start: datetime,
    end: datetime,
) -> Dict[str, Dict[str, Any]]:
    """Get AI vs human split by channel."""
    channels = ["email", "chat", "sms", "voice", "slack", "webchat"]
    result = {}

    for channel in channels:
        split = _get_channel_type_split(db, company_id, start, end, channel)
        if split["total"] > 0:
            result[channel] = split

    return result


def _get_channel_type_split(
    db: Session,
    company_id: str,
    start: datetime,
    end: datetime,
    channel: str,
) -> Dict[str, Any]:
    """Get AI vs human split for a specific channel."""
    # Get ticket IDs for this channel
    channel_tickets = db.query(Ticket.id).filter(
        Ticket.company_id == company_id,
        Ticket.created_at >= start,
        Ticket.created_at < end,
    )

    # Filter by channel if the attribute exists
    if hasattr(Ticket, "channel"):
        channel_tickets = channel_tickets.filter(Ticket.channel == channel)

    ticket_ids = [t.id for t in channel_tickets.limit(1000).all()]

    if not ticket_ids:
        return {
            "ai_tickets": 0,
            "human_tickets": 0,
            "ai_pct": 0,
            "human_pct": 0,
            "total": 0,
        }

    ai = (
        db.query(func.count(TicketAssignment.id))
        .filter(
            TicketAssignment.company_id == company_id,
            TicketAssignment.ticket_id.in_(ticket_ids),
            TicketAssignment.assignee_type == "ai",
        )
        .scalar()
        or 0
    )

    human = (
        db.query(func.count(TicketAssignment.id))
        .filter(
            TicketAssignment.company_id == company_id,
            TicketAssignment.ticket_id.in_(ticket_ids),
            TicketAssignment.assignee_type == "human",
        )
        .scalar()
        or 0
    )

    total = ai + human
    return {
        "ai_tickets": ai,
        "human_tickets": human,
        "ai_pct": round((ai / total * 100), 1) if total > 0 else 0,
        "human_pct": round((human / total * 100), 1) if total > 0 else 0,
        "total": total,
    }


def _get_category_split(
    db: Session,
    company_id: str,
    start: datetime,
    end: datetime,
) -> List[Dict[str, Any]]:
    """Get AI vs human split by category."""
    try:
        categories = (
            db.query(Ticket.category, func.count(Ticket.id))
            .filter(
                Ticket.company_id == company_id,
                Ticket.created_at >= start,
                Ticket.created_at < end,
                Ticket.category.isnot(None),
            )
            .group_by(Ticket.category)
            .order_by(
                func.count(Ticket.id).desc(),
            )
            .limit(10)
            .all()
        )

        result = []
        for cat, total_count in categories:
            cat_tickets = (
                db.query(Ticket.id)
                .filter(
                    Ticket.company_id == company_id,
                    Ticket.created_at >= start,
                    Ticket.created_at < end,
                    Ticket.category == cat,
                )
                .limit(500)
                .all()
            )
            ticket_ids = [t.id for t in cat_tickets]

            ai = 0
            human = 0
            if ticket_ids:
                ai = (
                    db.query(func.count(TicketAssignment.id))
                    .filter(
                        TicketAssignment.company_id == company_id,
                        TicketAssignment.ticket_id.in_(ticket_ids),
                        TicketAssignment.assignee_type == "ai",
                    )
                    .scalar()
                    or 0
                )

                human = (
                    db.query(func.count(TicketAssignment.id))
                    .filter(
                        TicketAssignment.company_id == company_id,
                        TicketAssignment.ticket_id.in_(ticket_ids),
                        TicketAssignment.assignee_type == "human",
                    )
                    .scalar()
                    or 0
                )

            split_total = ai + human
            result.append(
                {
                    "category": cat,
                    "total_tickets": total_count,
                    "ai_tickets": ai,
                    "human_tickets": human,
                    "ai_pct": (
                        round((ai / split_total * 100), 1) if split_total > 0 else 0
                    ),
                    "human_pct": (
                        round((human / split_total * 100), 1) if split_total > 0 else 0
                    ),
                }
            )

        return result

    except Exception:
        return []


def _get_resolution_rate_by_type(
    db: Session,
    company_id: str,
    start: datetime,
    end: datetime,
    assignee_type: str,
) -> float:
    """Get resolution rate for AI or human agents."""
    try:
        # Get ticket IDs assigned to this type
        assigned_ids = (
            db.query(TicketAssignment.ticket_id)
            .filter(
                TicketAssignment.company_id == company_id,
                TicketAssignment.assigned_at >= start,
                TicketAssignment.assigned_at < end,
                TicketAssignment.assignee_type == assignee_type,
            )
            .distinct()
            .limit(1000)
            .all()
        )

        if not assigned_ids:
            return 0.0

        ticket_ids = [t[0] for t in assigned_ids]

        resolved = (
            db.query(func.count(Ticket.id))
            .filter(
                Ticket.id.in_(ticket_ids),
                Ticket.status.in_(
                    [
                        TicketStatus.resolved.value,
                        TicketStatus.closed.value,
                    ]
                ),
            )
            .scalar()
            or 0
        )

        return (resolved / len(ticket_ids)) * 100 if ticket_ids else 0.0

    except Exception:
        return 0.0


def _empty_workforce_response() -> Dict[str, Any]:
    """Return an empty workforce response."""
    return {
        "current_split": {
            "period": "",
            "ai_tickets": 0,
            "human_tickets": 0,
            "ai_pct": 0,
            "human_pct": 0,
            "total": 0,
        },
        "daily_trend": [],
        "by_channel": {},
        "by_category": [],
        "ai_resolution_rate": 0.0,
        "human_resolution_rate": 0.0,
    }
