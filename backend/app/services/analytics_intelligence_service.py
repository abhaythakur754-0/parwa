"""
PARWA Analytics Intelligence Services (Week 15 — Dashboard + Analytics)

Services for intelligent analytics features:
- F-042: Growth Nudge Alert — usage pattern analysis
- F-043: Ticket Volume Forecast — predictive analytics
- F-044: CSAT Trends — customer satisfaction analytics

Building Codes: BC-001 (multi-tenant), BC-007 (AI model),
               BC-011 (auth), BC-012 (error handling)
"""

from __future__ import annotations

import statistics
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.logger import get_logger
from database.models.tickets import (
    Ticket,
    TicketFeedback,
    TicketAssignment,
    SLATimer,
)

logger = get_logger("analytics_intelligence_service")

# ══════════════════════════════════════════════════════════════════
# F-042: GROWTH NUDGE ALERT — Usage Pattern Analysis
# ══════════════════════════════════════════════════════════════════

# Nudge detection thresholds
LOW_AI_UTILIZATION_THRESHOLD = 0.30  # AI handles < 30% of tickets
HIGH_HUMAN_WORKLOAD_THRESHOLD = 50   # Human handles > 50 tickets/week
CHANNEL_NOT_USED_THRESHOLD = 7       # Channel not used in 7+ days
CSAT_DECLINE_THRESHOLD = 0.5        # CSAT dropped by 0.5+ points
SCALING_THRESHOLD = 1.5             # Volume increased 50%+ week over week


def get_growth_nudges(
    company_id: str,
    db: Session,
) -> Dict[str, Any]:
    """Analyze usage patterns and generate growth nudges.

    Detects underutilized features, scaling needs, upgrade
    opportunities, and feature discovery suggestions.

    F-042: Growth Nudge Alert
    BC-001: Scoped by company_id.
    """
    try:
        now = datetime.now(timezone.utc)
        nudges: List[Dict[str, Any]] = []

        # 1. Low AI utilization
        ai_nudge = _check_ai_utilization(company_id, db, now)
        if ai_nudge:
            nudges.append(ai_nudge)

        # 2. Scaling alert — volume increase
        scaling_nudge = _check_scaling_need(company_id, db, now)
        if scaling_nudge:
            nudges.append(scaling_nudge)

        # 3. Underutilized channels
        channel_nudges = _check_channel_usage(company_id, db, now)
        nudges.extend(channel_nudges)

        # 4. CSAT decline
        csat_nudge = _check_csat_decline(company_id, db, now)
        if csat_nudge:
            nudges.append(csat_nudge)

        # 5. Feature discovery — knowledge base empty
        kb_nudge = _check_knowledge_base_usage(company_id, db, now)
        if kb_nudge:
            nudges.append(kb_nudge)

        # 6. SLA breach pattern
        sla_nudge = _check_sla_pattern(company_id, db, now)
        if sla_nudge:
            nudges.append(sla_nudge)

        # Sort by severity
        severity_order = {
            "urgent": 0,
            "recommendation": 1,
            "suggestion": 2,
            "info": 3}
        nudges.sort(
            key=lambda n: severity_order.get(
                n.get(
                    "severity",
                    "info"),
                4))

        return {
            "nudges": nudges,
            "total": len(nudges),
            "dismissed_count": 0,
        }

    except Exception as exc:
        logger.error(
            "growth_nudge_error",
            company_id=company_id,
            error=str(exc),
        )
        return {"nudges": [], "total": 0, "dismissed_count": 0}


def _check_ai_utilization(
    company_id: str, db: Session, now: datetime,
) -> Optional[Dict[str, Any]]:
    """Check if AI is underutilized."""
    try:
        last_7d = now - timedelta(days=7)
        ai_count = db.query(func.count(TicketAssignment.id)).filter(
            TicketAssignment.company_id == company_id,
            TicketAssignment.assigned_at >= last_7d,
            TicketAssignment.assignee_type == "ai",
        ).scalar() or 0

        human_count = db.query(func.count(TicketAssignment.id)).filter(
            TicketAssignment.company_id == company_id,
            TicketAssignment.assigned_at >= last_7d,
            TicketAssignment.assignee_type == "human",
        ).scalar() or 0

        total = ai_count + human_count
        if total > 0 and (ai_count / total) < LOW_AI_UTILIZATION_THRESHOLD:
            return {
                "nudge_id": str(uuid.uuid4()),
                "nudge_type": "underutilized",
                "severity": "suggestion",
                "title": "AI is handling a small portion of your tickets",
                "message": (
                    f"AI resolved {ai_count} of {total} tickets this week "
                    f"({round(ai_count / total * 100, 1)}%). "
                    "Consider expanding AI to more categories to reduce agent workload."
                ),
                "action_label": "Review AI Settings",
                "action_url": "/settings/ai",
                "dismissed": False,
                "detected_at": now.isoformat(),
            }
    except Exception:
        pass
    return None


def _check_scaling_need(
    company_id: str, db: Session, now: datetime,
) -> Optional[Dict[str, Any]]:
    """Check if ticket volume is scaling rapidly."""
    try:
        this_week = now - timedelta(days=7)
        last_week = now - timedelta(days=14)

        this_count = db.query(func.count(Ticket.id)).filter(
            Ticket.company_id == company_id,
            Ticket.created_at >= this_week,
            Ticket.created_at < now,
        ).scalar() or 0

        last_count = db.query(func.count(Ticket.id)).filter(
            Ticket.company_id == company_id,
            Ticket.created_at >= last_week,
            Ticket.created_at < this_week,
        ).scalar() or 0

        if last_count > 0 and this_count >= last_count * SCALING_THRESHOLD:
            return {
                "nudge_id": str(uuid.uuid4()),
                "nudge_type": "scaling",
                "severity": "recommendation",
                "title": "Ticket volume is growing fast",
                "message": (
                    f"Volume increased from {last_count} to {this_count} tickets/week "
                    f"(+{round((this_count - last_count) / last_count * 100, 0)}%). "
                    "Consider upgrading your plan or adding more AI agents."
                ),
                "action_label": "View Plans",
                "action_url": "/billing/plans",
                "dismissed": False,
                "detected_at": now.isoformat(),
            }
    except Exception:
        pass
    return None


def _check_channel_usage(
    company_id: str, db: Session, now: datetime,
) -> List[Dict[str, Any]]:
    """Check for underutilized channels."""
    nudges = []
    channels = [
        ("email", "Email"),
        ("chat", "Chat Widget"),
        ("sms", "SMS"),
        ("voice", "Voice"),
        ("slack", "Slack"),
        ("webchat", "Webchat"),
    ]

    for channel_key, channel_name in channels:
        try:
            cutoff = now - timedelta(days=CHANNEL_NOT_USED_THRESHOLD)
            count = 0

            if hasattr(Ticket, "channel"):
                count = db.query(func.count(Ticket.id)).filter(
                    Ticket.company_id == company_id,
                    Ticket.channel == channel_key,
                    Ticket.created_at >= cutoff,
                ).scalar() or 0

            if count == 0:
                nudges.append({
                    "nudge_id": str(uuid.uuid4()),
                    "nudge_type": "feature_discovery",
                    "severity": "info",
                    "title": f"{channel_name} channel has no recent activity",
                    "message": (
                        f"No tickets received via {channel_name} in the last "
                        f"{CHANNEL_NOT_USED_THRESHOLD} days. "
                        "Activate it to reach more customers."
                    ),
                    "action_label": "Configure Channel",
                    "action_url": f"/settings/channels/{channel_key}",
                    "dismissed": False,
                    "detected_at": now.isoformat(),
                })
        except Exception:
            continue

    return nudges


def _check_csat_decline(
    company_id: str, db: Session, now: datetime,
) -> Optional[Dict[str, Any]]:
    """Check if CSAT is declining."""
    try:
        this_week_start = now - timedelta(days=7)
        last_week_start = now - timedelta(days=14)

        this_csat = db.query(func.avg(TicketFeedback.rating)).join(
            Ticket, Ticket.id == TicketFeedback.ticket_id,
        ).filter(
            Ticket.company_id == company_id,
            TicketFeedback.created_at >= this_week_start,
        ).scalar()

        last_csat = db.query(func.avg(TicketFeedback.rating)).join(
            Ticket, Ticket.id == TicketFeedback.ticket_id,
        ).filter(
            Ticket.company_id == company_id,
            TicketFeedback.created_at >= last_week_start,
            TicketFeedback.created_at < this_week_start,
        ).scalar()

        if this_csat is not None and last_csat is not None:
            decline = float(last_csat) - float(this_csat)
            if decline >= CSAT_DECLINE_THRESHOLD:
                return {
                    "nudge_id": str(uuid.uuid4()),
                    "nudge_type": "underutilized",
                    "severity": "recommendation",
                    "title": "Customer satisfaction is declining",
                    "message": (
                        f"CSAT dropped from {round(float(last_csat), 2)} to "
                        f"{round(float(this_csat), 2)} this week "
                        f"(-{round(decline, 2)} points). "
                        "Review recent AI responses and consider retraining."
                    ),
                    "action_label": "View CSAT Trends",
                    "action_url": "/dashboard/analytics/csat",
                    "dismissed": False,
                    "detected_at": now.isoformat(),
                }
    except Exception:
        pass
    return None


def _check_knowledge_base_usage(
    company_id: str, db: Session, now: datetime,
) -> Optional[Dict[str, Any]]:
    """Check if knowledge base is being utilized."""
    try:
        from database.models.knowledge_base import KnowledgeBase
        count = db.query(func.count(KnowledgeBase.id)).filter(
            KnowledgeBase.company_id == company_id,
        ).scalar() or 0

        if count == 0:
            return {
                "nudge_id": str(uuid.uuid4()),
                "nudge_type": "feature_discovery",
                "severity": "suggestion",
                "title": "No knowledge base articles yet",
                "message": (
                    "Adding knowledge base articles significantly improves "
                    "AI response accuracy. Upload your FAQ, product docs, "
                    "or support guides to get started."
                ),
                "action_label": "Upload Articles",
                "action_url": "/settings/knowledge-base",
                "dismissed": False,
                "detected_at": now.isoformat(),
            }
    except Exception:
        pass
    return None


def _check_sla_pattern(
    company_id: str, db: Session, now: datetime,
) -> Optional[Dict[str, Any]]:
    """Check for SLA breach patterns."""
    try:
        last_7d = now - timedelta(days=7)
        breached = db.query(func.count(SLATimer.id)).filter(
            SLATimer.company_id == company_id,
            SLATimer.created_at >= last_7d,
            SLATimer.is_breached is True,  # noqa: E712
        ).scalar() or 0

        total = db.query(func.count(SLATimer.id)).filter(
            SLATimer.company_id == company_id,
            SLATimer.created_at >= last_7d,
        ).scalar() or 0

        if total > 0 and (breached / total) > 0.20:
            return {
                "nudge_id": str(uuid.uuid4()),
                "nudge_type": "scaling",
                "severity": "urgent",
                "title": "SLA breach rate is high",
                "message": (
                    f"{breached} of {total} tickets ({round(breached / total * 100, 1)}%) "
                    "breached SLA this week. Consider adding more agents or "
                    "adjusting SLA targets."
                ),
                "action_label": "Review SLA Settings",
                "action_url": "/settings/sla",
                "dismissed": False,
                "detected_at": now.isoformat(),
            }
    except Exception:
        pass
    return None


# ══════════════════════════════════════════════════════════════════
# F-043: TICKET VOLUME FORECAST — Predictive Analytics
# ══════════════════════════════════════════════════════════════════

FORECAST_DAYS = 14  # Predict 14 days ahead
HISTORICAL_DAYS = 30  # Use 30 days of history


def get_ticket_forecast(
    company_id: str,
    db: Session,
    forecast_days: int = FORECAST_DAYS,
    historical_days: int = HISTORICAL_DAYS,
) -> Dict[str, Any]:
    """Predict future ticket volume using statistical methods.

    Uses moving average and linear regression for forecasting.
    Provides confidence bounds and trend detection.

    F-043: Ticket Volume Forecast
    BC-001: Scoped by company_id.
    """
    try:
        now = datetime.now(timezone.utc)
        historical_start = now - timedelta(days=historical_days)

        # Get daily historical data
        daily_counts = _get_daily_volume(db, company_id, historical_start, now)

        if not daily_counts:
            return _empty_forecast_response()

        # Calculate forecast
        forecast_values = _moving_average_forecast(daily_counts, forecast_days)
        linear_forecast = _linear_regression_forecast(
            daily_counts, forecast_days)

        # Use linear regression as primary, MA as secondary
        primary_forecast = linear_forecast
        model_type = "linear_regression"

        # Build historical points
        historical = []
        for i, (date, count) in enumerate(daily_counts):
            historical.append({
                "date": date,
                "predicted": float(count),
                "actual": float(count),
            })

        # Build forecast points
        forecast = []
        last_date = datetime.strptime(daily_counts[-1][0], "%Y-%m-%d")
        for i, value in enumerate(primary_forecast):
            future_date = last_date + timedelta(days=i + 1)
            # Confidence bounds widen over time
            std_dev = _estimate_std_dev(daily_counts)
            bound_factor = 1.96 * (1 + i * 0.1)  # Widening bounds
            lower = max(0, value - bound_factor * std_dev)
            upper = value + bound_factor * std_dev

            forecast.append({
                "date": future_date.strftime("%Y-%m-%d"),
                "predicted": round(value, 1),
                "lower_bound": round(lower, 1),
                "upper_bound": round(upper, 1),
                "actual": None,
            })

        # Detect seasonality (day-of-week pattern)
        seasonality = _detect_seasonality(daily_counts)

        # Trend direction
        if len(primary_forecast) > 1:
            first_half = statistics.mean(
                primary_forecast[:len(primary_forecast) // 2])
            second_half = statistics.mean(
                primary_forecast[len(primary_forecast) // 2:])
            if second_half > first_half * 1.05:
                trend_direction = "increasing"
            elif second_half < first_half * 0.95:
                trend_direction = "decreasing"
            else:
                trend_direction = "stable"
        else:
            trend_direction = "stable"

        avg_daily = statistics.mean(
            [c for _, c in daily_counts]) if daily_counts else 0

        return {
            "historical": historical,
            "forecast": forecast,
            "model_type": model_type,
            "confidence_level": 0.95,
            "seasonality_detected": seasonality,
            "trend_direction": trend_direction,
            "avg_daily_volume": round(avg_daily, 1),
        }

    except Exception as exc:
        logger.error(
            "ticket_forecast_error",
            company_id=company_id,
            error=str(exc),
        )
        return _empty_forecast_response()


def _get_daily_volume(
    db: Session, company_id: str, start: datetime, end: datetime,
) -> List[Tuple[str, int]]:
    """Get daily ticket volume as list of (date_str, count) tuples."""
    result = []
    current = start
    while current < end:
        next_day = current + timedelta(days=1)
        count = db.query(func.count(Ticket.id)).filter(
            Ticket.company_id == company_id,
            Ticket.created_at >= current,
            Ticket.created_at < next_day,
        ).scalar() or 0
        result.append((current.strftime("%Y-%m-%d"), count))
        current = next_day
    return result


def _moving_average_forecast(
    data: List[Tuple[str, int]], forecast_days: int,
) -> List[float]:
    """Simple moving average forecast."""
    if not data:
        return [0.0] * forecast_days

    window = min(7, len(data))
    values = [c for _, c in data]
    recent_avg = statistics.mean(values[-window:])

    # Trend adjustment
    if len(values) >= 14:
        recent_week = statistics.mean(values[-7:])
        previous_week = statistics.mean(values[-14:-7])
        if previous_week > 0:
            trend = (recent_week - previous_week) / previous_week
        else:
            trend = 0
    else:
        trend = 0

    forecast = []
    for i in range(forecast_days):
        adjusted = recent_avg * (1 + trend * 0.1 * i)
        forecast.append(max(0, round(adjusted, 1)))

    return forecast


def _linear_regression_forecast(
    data: List[Tuple[str, int]], forecast_days: int,
) -> List[float]:
    """Linear regression forecast."""
    if len(data) < 2:
        return _moving_average_forecast(data, forecast_days)

    n = len(data)
    values = [float(c) for _, c in data]
    x = list(range(n))

    # Calculate regression coefficients
    x_mean = statistics.mean(x)
    y_mean = statistics.mean(values)

    numerator = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, values))
    denominator = sum((xi - x_mean) ** 2 for xi in x)

    if denominator == 0:
        return _moving_average_forecast(data, forecast_days)

    slope = numerator / denominator
    intercept = y_mean - slope * x_mean

    forecast = []
    for i in range(forecast_days):
        predicted = intercept + slope * (n + i)
        forecast.append(max(0, round(predicted, 1)))

    return forecast


def _estimate_std_dev(data: List[Tuple[str, int]]) -> float:
    """Estimate standard deviation of daily counts."""
    if len(data) < 2:
        return 0.0
    values = [float(c) for _, c in data]
    return statistics.stdev(values) if len(values) >= 2 else 0.0


def _detect_seasonality(data: List[Tuple[str, int]]) -> bool:
    """Detect day-of-week seasonality pattern."""
    if len(data) < 14:
        return False

    # Group by day of week
    dow_sums: Dict[int, List[float]] = {}
    for date_str, count in data:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        dow = dt.weekday()
        if dow not in dow_sums:
            dow_sums[dow] = []
        dow_sums[dow].append(float(count))

    # Check if there's significant variance between days
    if len(dow_sums) < 5:
        return False

    dow_means = [statistics.mean(v) for v in dow_sums.values() if v]
    if len(dow_means) < 3:
        return False

    overall_mean = statistics.mean(dow_means)
    if overall_mean == 0:
        return False

    # Check coefficient of variation
    std = statistics.stdev(dow_means) if len(dow_means) >= 2 else 0
    cv = std / overall_mean

    return cv > 0.2  # >20% variation between days = seasonality


def _empty_forecast_response() -> Dict[str, Any]:
    """Return an empty forecast response."""
    return {
        "historical": [],
        "forecast": [],
        "model_type": "none",
        "confidence_level": 0.95,
        "seasonality_detected": False,
        "trend_direction": "stable",
        "avg_daily_volume": 0,
    }


# ══════════════════════════════════════════════════════════════════
# F-044: CSAT TRENDS — Customer Satisfaction Analytics
# ══════════════════════════════════════════════════════════════════


def get_csat_trends(
    company_id: str,
    db: Session,
    days: int = 30,
) -> Dict[str, Any]:
    """Get CSAT trend analytics.

    Provides daily CSAT averages, breakdowns by agent/category/channel,
    rating distribution, and trend direction analysis.

    F-044: CSAT Trends
    BC-001: Scoped by company_id.
    """
    try:
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days)
        prev_start = start - timedelta(days=days)

        # Daily trend
        daily_trend = _get_csat_daily_trend(db, company_id, start, now)

        # Overall averages
        current_avg = _get_overall_csat(db, company_id, start, now)
        previous_avg = _get_overall_csat(db, company_id, prev_start, start)
        total_ratings = _count_csat_total(db, company_id, start, now)

        # Trend direction
        change_vs_prev = None
        if current_avg is not None and previous_avg is not None:
            change_vs_prev = round(current_avg - previous_avg, 2)
            if change_vs_prev > 0.1:
                trend_direction = "improving"
            elif change_vs_prev < -0.1:
                trend_direction = "declining"
            else:
                trend_direction = "stable"
        else:
            trend_direction = "stable"

        # By agent
        by_agent = _get_csat_by_agent(db, company_id, start, now)

        # By category
        by_category = _get_csat_by_category(db, company_id, start, now)

        # By channel
        by_channel = _get_csat_by_channel(db, company_id, start, now)

        return {
            "daily_trend": daily_trend,
            "overall_avg": round(current_avg, 2) if current_avg else 0,
            "overall_total": total_ratings,
            "by_agent": by_agent,
            "by_category": by_category,
            "by_channel": by_channel,
            "trend_direction": trend_direction,
            "change_vs_previous_period": change_vs_prev,
        }

    except Exception as exc:
        logger.error(
            "csat_trends_error",
            company_id=company_id,
            error=str(exc),
        )
        return _empty_csat_response()


def _get_csat_daily_trend(
    db: Session, company_id: str, start: datetime, end: datetime,
) -> List[Dict[str, Any]]:
    """Get daily CSAT trend with rating distribution."""
    trend = []
    current = start
    while current < end:
        next_day = current + timedelta(days=1)

        # Average rating
        avg = db.query(func.avg(TicketFeedback.rating)).join(
            Ticket, Ticket.id == TicketFeedback.ticket_id,
        ).filter(
            Ticket.company_id == company_id,
            TicketFeedback.created_at >= current,
            TicketFeedback.created_at < next_day,
        ).scalar()

        # Total ratings
        total = db.query(func.count(TicketFeedback.id)).join(
            Ticket, Ticket.id == TicketFeedback.ticket_id,
        ).filter(
            Ticket.company_id == company_id,
            TicketFeedback.created_at >= current,
            TicketFeedback.created_at < next_day,
        ).scalar() or 0

        # Distribution (1-5)
        distribution = {}
        for rating in range(1, 6):
            count = db.query(func.count(TicketFeedback.id)).join(
                Ticket, Ticket.id == TicketFeedback.ticket_id,
            ).filter(
                Ticket.company_id == company_id,
                TicketFeedback.created_at >= current,
                TicketFeedback.created_at < next_day,
                TicketFeedback.rating == rating,
            ).scalar() or 0
            distribution[str(rating)] = count

        trend.append({
            "date": current.strftime("%Y-%m-%d"),
            "avg_rating": round(float(avg), 2) if avg else 0,
            "total_ratings": total,
            "distribution": distribution,
        })

        current = next_day

    return trend


def _get_overall_csat(
    db: Session, company_id: str, start: datetime, end: datetime,
) -> Optional[float]:
    """Get overall average CSAT for a period."""
    result = db.query(func.avg(TicketFeedback.rating)).join(
        Ticket, Ticket.id == TicketFeedback.ticket_id,
    ).filter(
        Ticket.company_id == company_id,
        TicketFeedback.created_at >= start,
        TicketFeedback.created_at < end,
    ).scalar()
    return float(result) if result else None


def _count_csat_total(
    db: Session, company_id: str, start: datetime, end: datetime,
) -> int:
    """Count total CSAT ratings."""
    return db.query(func.count(TicketFeedback.id)).join(
        Ticket, Ticket.id == TicketFeedback.ticket_id,
    ).filter(
        Ticket.company_id == company_id,
        TicketFeedback.created_at >= start,
        TicketFeedback.created_at < end,
    ).scalar() or 0


def _get_csat_by_agent(
    db: Session, company_id: str, start: datetime, end: datetime,
) -> List[Dict[str, Any]]:
    """Get CSAT breakdown by agent."""
    try:
        from database.models.core import User

        results = db.query(
            Ticket.assigned_to,
            func.avg(TicketFeedback.rating).label("avg_rating"),
            func.count(TicketFeedback.id).label("total_ratings"),
        ).join(
            TicketFeedback, Ticket.id == TicketFeedback.ticket_id,
        ).filter(
            Ticket.company_id == company_id,
            TicketFeedback.created_at >= start,
            TicketFeedback.created_at < end,
            Ticket.assigned_to.isnot(None),
        ).group_by(Ticket.assigned_to).order_by(
            func.avg(TicketFeedback.rating).desc(),
        ).limit(20).all()

        agent_ids = [r.assigned_to for r in results if r.assigned_to]
        users = {}
        if agent_ids:
            user_list = db.query(User).filter(User.id.in_(agent_ids)).all()
            users = {str(u.id): getattr(u, "name", None)
                     or u.email for u in user_list}

        return [
            {
                "dimension_name": users.get(str(r.assigned_to), str(r.assigned_to)),
                "avg_rating": round(float(r.avg_rating), 2) if r.avg_rating else 0,
                "total_ratings": r.total_ratings,
            }
            for r in results
        ]

    except Exception:
        return []


def _get_csat_by_category(
    db: Session, company_id: str, start: datetime, end: datetime,
) -> List[Dict[str, Any]]:
    """Get CSAT breakdown by ticket category."""
    try:
        results = db.query(
            Ticket.category,
            func.avg(TicketFeedback.rating).label("avg_rating"),
            func.count(TicketFeedback.id).label("total_ratings"),
        ).join(
            TicketFeedback, Ticket.id == TicketFeedback.ticket_id,
        ).filter(
            Ticket.company_id == company_id,
            TicketFeedback.created_at >= start,
            TicketFeedback.created_at < end,
            Ticket.category.isnot(None),
        ).group_by(Ticket.category).order_by(
            func.avg(TicketFeedback.rating).desc(),
        ).limit(10).all()

        return [{"dimension_name": r.category,
                 "avg_rating": round(float(r.avg_rating),
                                     2) if r.avg_rating else 0,
                 "total_ratings": r.total_ratings,
                 } for r in results]

    except Exception:
        return []


def _get_csat_by_channel(
    db: Session, company_id: str, start: datetime, end: datetime,
) -> List[Dict[str, Any]]:
    """Get CSAT breakdown by channel."""
    try:
        if not hasattr(Ticket, "channel"):
            return []

        results = db.query(
            Ticket.channel,
            func.avg(TicketFeedback.rating).label("avg_rating"),
            func.count(TicketFeedback.id).label("total_ratings"),
        ).join(
            TicketFeedback, Ticket.id == TicketFeedback.ticket_id,
        ).filter(
            Ticket.company_id == company_id,
            TicketFeedback.created_at >= start,
            TicketFeedback.created_at < end,
            Ticket.channel.isnot(None),
        ).group_by(Ticket.channel).order_by(
            func.avg(TicketFeedback.rating).desc(),
        ).limit(10).all()

        return [{"dimension_name": r.channel,
                 "avg_rating": round(float(r.avg_rating),
                                     2) if r.avg_rating else 0,
                 "total_ratings": r.total_ratings,
                 } for r in results]

    except Exception:
        return []


def _empty_csat_response() -> Dict[str, Any]:
    """Return an empty CSAT response."""
    return {
        "daily_trend": [],
        "overall_avg": 0,
        "overall_total": 0,
        "by_agent": [],
        "by_category": [],
        "by_channel": [],
        "trend_direction": "stable",
        "change_vs_previous_period": None,
    }
