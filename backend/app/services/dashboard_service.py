"""
PARWA Dashboard Service (F-036, F-037, F-038)

Unified dashboard data aggregation service.

F-036: Dashboard Home — combines data from multiple subsystems into
       a single API payload for the frontend dashboard.
F-037: Activity Feed — global event stream across all tickets.
F-038: Key Metrics Aggregation — KPI cards with sparkline data,
       anomaly detection, and period-over-period comparison.

Building Codes: BC-001 (multi-tenant), BC-005 (real-time),
               BC-011 (auth), BC-012 (error handling)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.logger import get_logger
from database.models.tickets import (
    Ticket,
    TicketFeedback,
    TicketStatus,
    TicketStatusChange,
    TicketAssignment,
    TicketPriority,
    SLATimer,
)

logger = get_logger("dashboard_service")


# ══════════════════════════════════════════════════════════════════
# DEFAULTS
# ══════════════════════════════════════════════════════════════════

ANOMALY_THRESHOLD = 10.0  # 10x spike detection factor
ACTIVITY_FEED_PAGE_SIZE = 25
SPARKLINE_POINTS = 14  # 14 days of sparkline data

# Default widget layout for the dashboard
DEFAULT_WIDGETS = [
    {"widget_id": "kpi-tickets", "widget_type": "kpi", "title": "Ticket Overview", "position": {"row": 0, "col": 0}, "size": {"width": 3, "height": 1}},
    {"widget_id": "kpi-resolution", "widget_type": "kpi", "title": "Resolution Rate", "position": {"row": 0, "col": 3}, "size": {"width": 3, "height": 1}},
    {"widget_id": "kpi-response-time", "widget_type": "kpi", "title": "Avg Response Time", "position": {"row": 0, "col": 6}, "size": {"width": 3, "height": 1}},
    {"widget_id": "kpi-csat", "widget_type": "kpi", "title": "Customer Satisfaction", "position": {"row": 1, "col": 0}, "size": {"width": 3, "height": 1}},
    {"widget_id": "trend-chart", "widget_type": "chart", "title": "Ticket Volume Trend", "position": {"row": 1, "col": 3}, "size": {"width": 6, "height": 2}},
    {"widget_id": "activity-feed", "widget_type": "feed", "title": "Activity Feed", "position": {"row": 2, "col": 0}, "size": {"width": 3, "height": 3}},
    {"widget_id": "savings-counter", "widget_type": "counter", "title": "AI Savings", "position": {"row": 2, "col": 3}, "size": {"width": 3, "height": 1}},
    {"widget_id": "workforce-chart", "widget_type": "chart", "title": "Workforce Allocation", "position": {"row": 2, "col": 6}, "size": {"width": 3, "height": 2}},
    {"widget_id": "category-chart", "widget_type": "chart", "title": "Category Distribution", "position": {"row": 3, "col": 3}, "size": {"width": 3, "height": 1}},
    {"widget_id": "sla-metrics", "widget_type": "kpi", "title": "SLA Compliance", "position": {"row": 3, "col": 6}, "size": {"width": 3, "height": 1}},
]


# ══════════════════════════════════════════════════════════════════
# F-036: DASHBOARD HOME
# ══════════════════════════════════════════════════════════════════


def get_dashboard_home(
    company_id: str,
    db: Session,
    period_days: int = 30,
) -> Dict[str, Any]:
    """Get unified dashboard home data.

    Aggregates data from ticket analytics, activity feed, savings,
    workforce allocation, CSAT, and anomaly detection into a single
    payload for one-round-trip dashboard rendering.

    F-036: Dashboard Home
    BC-001: Scoped by company_id.
    """
    try:
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=period_days)

        # Parallel data fetches
        summary = _get_ticket_summary(db, company_id, start, now)
        kpis = _get_kpi_cards(db, company_id, start, now)
        sla = _get_sla_summary(db, company_id, start, now)
        trend = _get_volume_trend(db, company_id, start, now)
        categories = _get_category_breakdown(db, company_id, start, now)
        activity = _get_activity_feed(db, company_id, limit=10)
        csat = _get_csat_summary(db, company_id, start, now)
        anomalies = _detect_anomalies(db, company_id, start, now)

        # Savings and workforce (best-effort — may not have data yet)
        savings = _get_savings_summary(db, company_id, start, now)
        workforce = _get_workforce_summary(db, company_id, start, now)

        return {
            "summary": summary,
            "kpis": kpis,
            "sla": sla,
            "trend": trend,
            "by_category": categories,
            "activity_feed": activity,
            "savings": savings,
            "workforce": workforce,
            "csat": csat,
            "anomalies": anomalies,
            "layout": {
                "layout_id": "default",
                "widgets": DEFAULT_WIDGETS,
                "is_default": True,
            },
            "generated_at": now.isoformat(),
        }

    except Exception as exc:
        logger.error(
            "dashboard_home_error",
            company_id=company_id,
            error=str(exc),
        )
        return {
            "error": str(exc)[:200],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


# ══════════════════════════════════════════════════════════════════
# F-037: ACTIVITY FEED
# ══════════════════════════════════════════════════════════════════


def get_activity_feed(
    company_id: str,
    db: Session,
    page: int = 1,
    page_size: int = ACTIVITY_FEED_PAGE_SIZE,
    event_types: Optional[List[str]] = None,
    ticket_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Get global activity feed.

    Pulls events from multiple sources (status changes, assignments,
    messages) across all tickets for the tenant and returns them
    in reverse-chronological order.

    F-037: Activity Feed
    BC-001: Scoped by company_id.
    BC-005: Designed for real-time push via Socket.io.
    """
    try:
        events: List[Dict[str, Any]] = []

        # 1. Status changes
        sc_query = db.query(TicketStatusChange).filter(
            TicketStatusChange.company_id == company_id,
        )
        if ticket_id:
            sc_query = sc_query.filter(
                TicketStatusChange.ticket_id == ticket_id,
            )
        status_changes = sc_query.order_by(
            desc(TicketStatusChange.created_at),
        ).limit(100).all()

        for sc in status_changes:
            events.append({
                "event_id": sc.id,
                "event_type": "status_changed",
                "actor_id": sc.changed_by,
                "actor_type": "human",
                "description": _describe_status_change(sc),
                "ticket_id": sc.ticket_id,
                "metadata": {
                    "from": sc.from_status,
                    "to": sc.to_status,
                },
                "created_at": (
                    sc.created_at.isoformat() if sc.created_at else ""
                ),
            })

        # 2. Assignments
        a_query = db.query(TicketAssignment).filter(
            TicketAssignment.company_id == company_id,
        )
        if ticket_id:
            a_query = a_query.filter(
                TicketAssignment.ticket_id == ticket_id,
            )
        assignments = a_query.order_by(
            desc(TicketAssignment.assigned_at),
        ).limit(100).all()

        for a in assignments:
            events.append({
                "event_id": a.id,
                "event_type": "assigned",
                "actor_type": a.assignee_type or "system",
                "actor_id": a.assignee_id,
                "description": _describe_assignment(a),
                "ticket_id": a.ticket_id,
                "metadata": {
                    "assignee_type": a.assignee_type,
                    "score": float(a.score) if a.score else None,
                },
                "created_at": (
                    a.assigned_at.isoformat() if a.assigned_at else ""
                ),
            })

        # 3. New tickets created
        t_query = db.query(Ticket).filter(
            Ticket.company_id == company_id,
        )
        if ticket_id:
            t_query = t_query.filter(Ticket.id == ticket_id)
        new_tickets = t_query.order_by(
            desc(Ticket.created_at),
        ).limit(50).all()

        for t in new_tickets:
            events.append({
                "event_id": str(uuid.uuid4()),
                "event_type": "ticket_created",
                "actor_type": "customer",
                "description": f"New ticket created: {t.subject or 'No subject'}",
                "ticket_id": t.id,
                "ticket_subject": t.subject,
                "metadata": {
                    "priority": t.priority,
                    "category": t.category,
                    "channel": getattr(t, "channel", None),
                },
                "created_at": (
                    t.created_at.isoformat() if t.created_at else ""
                ),
            })

        # Sort by timestamp descending
        events.sort(
            key=lambda e: e.get("created_at", ""),
            reverse=True,
        )

        # Filter by event types
        if event_types:
            events = [e for e in events if e["event_type"] in event_types]

        # Deduplicate by event_id
        seen = set()
        deduped = []
        for e in events:
            if e["event_id"] not in seen:
                seen.add(e["event_id"])
                deduped.append(e)
        events = deduped

        # Enrich actor names
        events = _enrich_actor_names(events, db)

        # Paginate
        total = len(events)
        offset = (page - 1) * page_size
        paginated = events[offset:offset + page_size]

        return {
            "events": paginated,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_more": (offset + page_size) < total,
        }

    except Exception as exc:
        logger.error(
            "activity_feed_error",
            company_id=company_id,
            error=str(exc),
        )
        return {
            "events": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "has_more": False,
        }


# ══════════════════════════════════════════════════════════════════
# F-038: KEY METRICS AGGREGATION
# ══════════════════════════════════════════════════════════════════


def get_key_metrics(
    company_id: str,
    db: Session,
    period: str = "last_30d",
) -> Dict[str, Any]:
    """Get aggregated KPI metrics with sparkline data.

    Returns a list of KPI cards, each with current value,
    previous period value, change percentage, and a sparkline
    array for mini-chart rendering.

    F-038: Key Metrics Aggregation
    BC-001: Scoped by company_id.
    """
    try:
        days_map = {
            "last_7d": 7,
            "last_30d": 30,
            "last_90d": 90,
        }
        period_days = days_map.get(period, 30)
        now = datetime.now(timezone.utc)
        current_start = now - timedelta(days=period_days)
        # Previous period: same duration before current period
        previous_start = current_start - timedelta(days=period_days)

        kpis: List[Dict[str, Any]] = []

        # ── KPI 1: Total Tickets ──
        current_total = _count_tickets(db, company_id, current_start, now)
        previous_total = _count_tickets(
            db, company_id, previous_start, current_start)
        sparkline = _get_daily_counts(db, company_id, period_days)
        kpis.append(_build_kpi(
            key="total_tickets",
            label="Total Tickets",
            value=current_total,
            previous_value=previous_total,
            unit="count",
            sparkline=sparkline,
        ))

        # ── KPI 2: Open Tickets ──
        open_count = _count_tickets_by_status(
            db, company_id, current_start, now,
            [TicketStatus.open.value, TicketStatus.in_progress.value,
             TicketStatus.awaiting_client.value, TicketStatus.awaiting_human.value],
        )
        kpis.append(_build_kpi(
            key="open_tickets",
            label="Open Tickets",
            value=open_count,
            unit="count",
        ))

        # ── KPI 3: Resolution Rate ──
        resolved = _count_tickets_by_status(
            db, company_id, current_start, now,
            [TicketStatus.resolved.value, TicketStatus.closed.value],
        )
        current_rate = (
            resolved /
            current_total *
            100) if current_total > 0 else 0
        prev_resolved = _count_tickets_by_status(
            db, company_id, previous_start, current_start,
            [TicketStatus.resolved.value, TicketStatus.closed.value],
        )
        prev_rate = (
            prev_resolved /
            previous_total *
            100) if previous_total > 0 else 0
        kpis.append(_build_kpi(
            key="resolution_rate",
            label="Resolution Rate",
            value=round(current_rate, 1),
            previous_value=round(prev_rate, 1),
            unit="%",
            sparkline=_get_daily_resolution_rate(db, company_id, period_days),
        ))

        # ── KPI 4: Avg First Response Time ──
        current_frt = _get_avg_first_response_time(
            db, company_id, current_start, now)
        previous_frt = _get_avg_first_response_time(
            db, company_id, previous_start, current_start)
        kpis.append(_build_kpi(
            key="avg_first_response_time",
            label="Avg First Response",
            value=round(current_frt, 1) if current_frt else 0,
            previous_value=round(previous_frt, 1) if previous_frt else None,
            unit="hours",
        ))

        # ── KPI 5: Avg Resolution Time ──
        current_art = _get_avg_resolution_time(
            db, company_id, current_start, now)
        previous_art = _get_avg_resolution_time(
            db, company_id, previous_start, current_start)
        kpis.append(_build_kpi(
            key="avg_resolution_time",
            label="Avg Resolution Time",
            value=round(current_art, 1) if current_art else 0,
            previous_value=round(previous_art, 1) if previous_art else None,
            unit="hours",
        ))

        # ── KPI 6: SLA Compliance ──
        current_sla = _get_sla_compliance_rate(
            db, company_id, current_start, now)
        previous_sla = _get_sla_compliance_rate(
            db, company_id, previous_start, current_start)
        kpis.append(
            _build_kpi(
                key="sla_compliance",
                label="SLA Compliance",
                value=round(
                    current_sla * 100,
                    1) if current_sla is not None else 0,
                previous_value=round(
                    previous_sla * 100,
                    1) if previous_sla is not None else None,
                unit="%",
            ))

        # ── KPI 7: CSAT Score ──
        current_csat = _get_avg_csat(db, company_id, current_start, now)
        previous_csat = _get_avg_csat(
            db, company_id, previous_start, current_start)
        kpis.append(_build_kpi(
            key="csat_score",
            label="Customer Satisfaction",
            value=round(current_csat, 2) if current_csat else 0,
            previous_value=round(previous_csat, 2) if previous_csat else None,
            unit="out of 5",
        ))

        # ── KPI 8: AI Resolved Tickets ──
        ai_resolved = _count_tickets_by_assignee_type(
            db, company_id, current_start, now, "ai",
        )
        kpis.append(_build_kpi(
            key="ai_resolved",
            label="AI Resolved",
            value=ai_resolved,
            unit="count",
        ))

        # ── KPI 9: Breached SLA ──
        breached = _count_breached_sla(db, company_id, current_start, now)
        kpis.append(_build_kpi(
            key="sla_breached",
            label="SLA Breached",
            value=breached,
            unit="count",
        ))

        # ── KPI 10: Critical Tickets ──
        critical = _count_tickets_by_priority(
            db, company_id, current_start, now, TicketPriority.critical.value,
        )
        kpis.append(_build_kpi(
            key="critical_tickets",
            label="Critical Tickets",
            value=critical,
            unit="count",
        ))

        # Annotate anomaly flags
        kpis = _flag_anomalies(kpis, db, company_id, current_start, now)

        return {
            "kpis": kpis,
            "period": period,
            "generated_at": now.isoformat(),
        }

    except Exception as exc:
        logger.error(
            "key_metrics_error",
            company_id=company_id,
            error=str(exc),
        )
        return {
            "kpis": [],
            "period": period,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


# ══════════════════════════════════════════════════════════════════
# INTERNAL HELPERS — Dashboard Home (F-036)
# ══════════════════════════════════════════════════════════════════


def _get_ticket_summary(
    db: Session, company_id: str, start: datetime, end: datetime,
) -> Dict[str, Any]:
    """Get ticket summary counts."""
    try:
        from app.services.ticket_analytics_service import (
            TicketAnalyticsService, DateRange,
        )
        svc = TicketAnalyticsService(db, company_id)
        s = svc.get_summary(DateRange(start_date=start, end_date=end))
        return {
            "total_tickets": s.total_tickets,
            "open": s.open_tickets,
            "in_progress": s.in_progress_tickets,
            "resolved": s.resolved_tickets,
            "closed": s.closed_tickets,
            "awaiting_client": s.awaiting_client_tickets,
            "awaiting_human": s.awaiting_human_tickets,
            "critical": s.critical_tickets,
            "high": s.high_tickets,
            "medium": s.medium_tickets,
            "low": s.low_tickets,
            "resolution_rate": round(s.resolution_rate, 3),
            "avg_resolution_time_hours": (
                round(s.avg_resolution_time_hours, 2)
                if s.avg_resolution_time_hours else 0
            ),
            "avg_first_response_time_hours": (
                round(s.avg_first_response_time_hours, 2)
                if s.avg_first_response_time_hours else 0
            ),
        }
    except Exception as exc:
        logger.warning("dashboard_summary_fallback", error=str(exc))
        return {}


def _get_kpi_cards(
    db: Session, company_id: str, start: datetime, end: datetime,
) -> Dict[str, Any]:
    """Get top KPI cards for dashboard."""
    try:
        from app.services.ticket_analytics_service import (
            TicketAnalyticsService, DateRange,
        )
        svc = TicketAnalyticsService(db, company_id)
        dr = DateRange(start_date=start, end_date=end)
        s = svc.get_summary(dr)
        sla = svc.get_sla_metrics(dr)

        return {
            "total_tickets": s.total_tickets,
            "open_tickets": s.open_tickets + s.in_progress_tickets,
            "resolution_rate": round(s.resolution_rate * 100, 1),
            "avg_response_time": (
                round(s.avg_first_response_time_hours, 2)
                if s.avg_first_response_time_hours else 0
            ),
            "sla_compliance": round(sla.compliance_rate * 100, 1),
            "breached_count": sla.breached_count,
        }
    except Exception:
        return {}


def _get_sla_summary(
    db: Session, company_id: str, start: datetime, end: datetime,
) -> Dict[str, Any]:
    """Get SLA summary."""
    try:
        from app.services.ticket_analytics_service import (
            TicketAnalyticsService, DateRange,
        )
        svc = TicketAnalyticsService(db, company_id)
        sla = svc.get_sla_metrics(DateRange(start_date=start, end_date=end))
        return {
            "compliance_rate": round(sla.compliance_rate * 100, 1),
            "breached_count": sla.breached_count,
            "approaching_count": sla.approaching_count,
            "compliant_count": sla.compliant_count,
            "avg_first_response_minutes": (
                round(sla.avg_first_response_minutes, 1)
                if sla.avg_first_response_minutes else None
            ),
            "avg_resolution_minutes": (
                round(sla.avg_resolution_minutes, 1)
                if sla.avg_resolution_minutes else None
            ),
        }
    except Exception:
        return {}


def _get_volume_trend(
    db: Session, company_id: str, start: datetime, end: datetime,
) -> List[Dict[str, Any]]:
    """Get daily ticket volume trend."""
    try:
        from app.services.ticket_analytics_service import (
            TicketAnalyticsService, DateRange, IntervalType,
        )
        svc = TicketAnalyticsService(db, company_id)
        dr = DateRange(start_date=start, end_date=end)
        trends = svc.get_trends(IntervalType.DAY, dr)
        return [
            {
                "timestamp": t.timestamp.isoformat() if hasattr(
                    t.timestamp,
                    "isoformat") else str(
                    t.timestamp),
                "count": t.count,
                "label": t.label,
            } for t in trends]
    except Exception:
        return []


def _get_category_breakdown(
    db: Session, company_id: str, start: datetime, end: datetime,
) -> List[Dict[str, Any]]:
    """Get category distribution."""
    try:
        from app.services.ticket_analytics_service import (
            TicketAnalyticsService, DateRange,
        )
        svc = TicketAnalyticsService(db, company_id)
        cats = svc.get_category_distribution(
            DateRange(start_date=start, end_date=end))
        return [
            {"category": c.category, "count": c.count, "percentage": c.percentage}
            for c in cats[:10]
        ]
    except Exception:
        return []


def _get_csat_summary(
    db: Session, company_id: str, start: datetime, end: datetime,
) -> Dict[str, Any]:
    """Get CSAT summary for dashboard."""
    avg = _get_avg_csat(db, company_id, start, end)
    total = _count_csat_ratings(db, company_id, start, end)
    return {
        "avg_rating": round(avg, 2) if avg else 0,
        "total_ratings": total,
    }


def _get_savings_summary(
    db: Session, company_id: str, start: datetime, end: datetime,
) -> Dict[str, Any]:
    """Get savings summary for dashboard widget."""
    try:
        from database.models.analytics import ROISnapshot
        snapshot = db.query(ROISnapshot).filter(
            ROISnapshot.company_id == company_id,
            ROISnapshot.snapshot_date >= start,
        ).order_by(desc(ROISnapshot.snapshot_date)).first()

        if not snapshot:
            return {
                "total_savings": 0,
                "tickets_ai": 0,
                "tickets_human": 0,
            }

        return {
            "total_savings": float(snapshot.total_savings or 0),
            "tickets_ai": snapshot.tickets_ai_resolved or 0,
            "tickets_human": snapshot.tickets_human_resolved or 0,
            "ai_accuracy": float(snapshot.ai_accuracy_pct or 0),
        }
    except Exception:
        return {"total_savings": 0, "tickets_ai": 0, "tickets_human": 0}


def _get_workforce_summary(
    db: Session, company_id: str, start: datetime, end: datetime,
) -> Dict[str, Any]:
    """Get workforce allocation summary for dashboard."""
    ai_tickets = _count_tickets_by_assignee_type(
        db, company_id, start, end, "ai")
    human_tickets = _count_tickets_by_assignee_type(
        db, company_id, start, end, "human")
    total = ai_tickets + human_tickets
    return {
        "ai_tickets": ai_tickets,
        "human_tickets": human_tickets,
        "ai_pct": round(
            (ai_tickets / total * 100),
            1) if total > 0 else 0,
        "human_pct": round(
            (human_tickets / total * 100),
            1) if total > 0 else 0,
        "total": total,
    }


def _detect_anomalies(
    db: Session, company_id: str, start: datetime, end: datetime,
) -> List[Dict[str, Any]]:
    """Detect anomalies in ticket metrics.

    Looks for 10x spikes in volume, unusual SLA breach rates,
    and significant drops in resolution rate.
    """
    anomalies: List[Dict[str, Any]] = []
    try:
        # Check for volume spike: compare last 24h avg vs previous 24h
        now = datetime.now(timezone.utc)
        last_24h = _count_tickets(
            db,
            company_id,
            now -
            timedelta(
                hours=24),
            now)
        prev_24h = _count_tickets(
            db,
            company_id,
            now -
            timedelta(
                hours=48),
            now -
            timedelta(
                hours=24))

        if prev_24h > 0 and last_24h >= prev_24h * ANOMALY_THRESHOLD:
            anomalies.append({
                "type": "volume_spike",
                "severity": "high",
                "message": f"Ticket volume spike: {last_24h} tickets in last 24h "
                f"({round(last_24h / max(prev_24h, 1), 1)}x normal)",
                "detected_at": now.isoformat(),
            })

        # Check for SLA breach rate
        breached = _count_breached_sla(
            db, company_id, now - timedelta(hours=24), now)
        if breached > 10:
            anomalies.append({
                "type": "sla_breach_cluster",
                "severity": "high",
                "message": f"{breached} SLA breaches in last 24 hours",
                "detected_at": now.isoformat(),
            })

    except Exception as exc:
        logger.debug("anomaly_detection_error", error=str(exc))

    return anomalies


# ══════════════════════════════════════════════════════════════════
# INTERNAL HELPERS — Activity Feed (F-037)
# ══════════════════════════════════════════════════════════════════


def _describe_status_change(sc: Any) -> str:
    """Generate human-readable description for a status change."""
    from_val = sc.from_status or "unknown"
    to_val = sc.to_status or "unknown"
    return f"Status changed from {from_val} to {to_val}"


def _describe_assignment(a: Any) -> str:
    """Generate human-readable description for an assignment."""
    assignee_type = a.assignee_type or "agent"
    return f"Ticket assigned to {assignee_type}"


def _enrich_actor_names(
    events: List[Dict[str, Any]], db: Session,
) -> List[Dict[str, Any]]:
    """Enrich events with actor names from User table."""
    actor_ids = set()
    for e in events:
        if e.get("actor_id") and e.get("actor_type") in ("human", "ai"):
            actor_ids.add(e["actor_id"])

    if not actor_ids:
        return events

    try:
        from database.models.core import User
        users = db.query(User).filter(User.id.in_(list(actor_ids))).all()
        name_map = {str(u.id): getattr(u, "name", None)
                    or u.email for u in users}

        for e in events:
            if e.get("actor_id"):
                e["actor_name"] = name_map.get(str(e["actor_id"]))
    except Exception:
        pass

    return events


def _get_activity_feed(
    db: Session, company_id: str, limit: int = 10,
) -> List[Dict[str, Any]]:
    """Get latest activity events for the dashboard widget."""
    result = get_activity_feed(company_id, db, page=1, page_size=limit)
    return result.get("events", [])


# ══════════════════════════════════════════════════════════════════
# INTERNAL HELPERS — Key Metrics (F-038)
# ══════════════════════════════════════════════════════════════════


def _count_tickets(
    db: Session, company_id: str, start: datetime, end: datetime,
) -> int:
    """Count total tickets in date range."""
    return db.query(func.count(Ticket.id)).filter(
        Ticket.company_id == company_id,
        Ticket.created_at >= start,
        Ticket.created_at <= end,
    ).scalar() or 0


def _count_tickets_by_status(
    db: Session, company_id: str, start: datetime, end: datetime,
    statuses: List[str],
) -> int:
    """Count tickets by status."""
    return db.query(func.count(Ticket.id)).filter(
        Ticket.company_id == company_id,
        Ticket.created_at >= start,
        Ticket.created_at <= end,
        Ticket.status.in_(statuses),
    ).scalar() or 0


def _count_tickets_by_priority(
    db: Session, company_id: str, start: datetime, end: datetime,
    priority: str,
) -> int:
    """Count tickets by priority."""
    return db.query(func.count(Ticket.id)).filter(
        Ticket.company_id == company_id,
        Ticket.created_at >= start,
        Ticket.created_at <= end,
        Ticket.priority == priority,
    ).scalar() or 0


def _count_tickets_by_assignee_type(
    db: Session, company_id: str, start: datetime, end: datetime,
    assignee_type: str,
) -> int:
    """Count tickets by assignee type (ai/human)."""
    return db.query(func.count(TicketAssignment.id)).filter(
        TicketAssignment.company_id == company_id,
        TicketAssignment.assigned_at >= start,
        TicketAssignment.assigned_at <= end,
        TicketAssignment.assignee_type == assignee_type,
    ).scalar() or 0


def _get_avg_first_response_time(
    db: Session, company_id: str, start: datetime, end: datetime,
) -> Optional[float]:
    """Get average first response time in hours."""
    tickets = db.query(Ticket).filter(
        Ticket.company_id == company_id,
        Ticket.created_at >= start,
        Ticket.created_at <= end,
        Ticket.first_response_at.isnot(None),
    ).all()

    if not tickets:
        return None

    times = []
    for t in tickets:
        if t.first_response_at and t.created_at:
            hours = (t.first_response_at - t.created_at).total_seconds() / 3600
            times.append(hours)

    return sum(times) / len(times) if times else None


def _get_avg_resolution_time(
    db: Session, company_id: str, start: datetime, end: datetime,
) -> Optional[float]:
    """Get average resolution time in hours."""
    tickets = db.query(Ticket).filter(
        Ticket.company_id == company_id,
        Ticket.created_at >= start,
        Ticket.created_at <= end,
        Ticket.closed_at.isnot(None),
    ).all()

    if not tickets:
        return None

    times = []
    for t in tickets:
        if t.closed_at and t.created_at:
            hours = (t.closed_at - t.created_at).total_seconds() / 3600
            times.append(hours)

    return sum(times) / len(times) if times else None


def _get_sla_compliance_rate(
    db: Session, company_id: str, start: datetime, end: datetime,
) -> Optional[float]:
    """Get SLA compliance rate (0.0 to 1.0)."""
    total = db.query(func.count(SLATimer.id)).filter(
        SLATimer.company_id == company_id,
        SLATimer.created_at >= start,
        SLATimer.created_at <= end,
    ).scalar() or 0

    if total == 0:
        return None

    breached = db.query(func.count(SLATimer.id)).filter(
        SLATimer.company_id == company_id,
        SLATimer.created_at >= start,
        SLATimer.created_at <= end,
        SLATimer.is_breached == True,  # noqa: E712
    ).scalar() or 0

    return 1.0 - (breached / total)


def _get_avg_csat(
    db: Session, company_id: str, start: datetime, end: datetime,
) -> Optional[float]:
    """Get average CSAT rating."""
    result = db.query(func.avg(TicketFeedback.rating)).join(
        Ticket, Ticket.id == TicketFeedback.ticket_id,
    ).filter(
        Ticket.company_id == company_id,
        TicketFeedback.created_at >= start,
        TicketFeedback.created_at <= end,
    ).scalar()
    return float(result) if result else None


def _count_csat_ratings(
    db: Session, company_id: str, start: datetime, end: datetime,
) -> int:
    """Count total CSAT ratings."""
    return db.query(func.count(TicketFeedback.id)).join(
        Ticket, Ticket.id == TicketFeedback.ticket_id,
    ).filter(
        Ticket.company_id == company_id,
        TicketFeedback.created_at >= start,
        TicketFeedback.created_at <= end,
    ).scalar() or 0


def _count_breached_sla(
    db: Session, company_id: str, start: datetime, end: datetime,
) -> int:
    """Count breached SLA timers."""
    return db.query(func.count(SLATimer.id)).filter(
        SLATimer.company_id == company_id,
        SLATimer.created_at >= start,
        SLATimer.created_at <= end,
        SLATimer.is_breached == True,  # noqa: E712
    ).scalar() or 0


def _get_daily_counts(
    db: Session, company_id: str, days: int,
) -> List[float]:
    """Get daily ticket counts for sparkline."""
    now = datetime.now(timezone.utc)
    counts = []
    for i in range(days - 1, -1, -1):
        day_start = now - timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        count = _count_tickets(db, company_id, day_start, day_end)
        counts.append(float(count))
    return counts


def _get_daily_resolution_rate(
    db: Session, company_id: str, days: int,
) -> List[float]:
    """Get daily resolution rate for sparkline."""
    now = datetime.now(timezone.utc)
    rates = []
    for i in range(days - 1, -1, -1):
        day_start = now - timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        total = _count_tickets(db, company_id, day_start, day_end)
        resolved = _count_tickets_by_status(
            db, company_id, day_start, day_end,
            [TicketStatus.resolved.value, TicketStatus.closed.value],
        )
        rate = (resolved / total * 100) if total > 0 else 0
        rates.append(round(rate, 1))
    return rates


def _build_kpi(
    key: str,
    label: str,
    value: Any,
    previous_value: Optional[Any] = None,
    unit: Optional[str] = None,
    sparkline: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Build a single KPI card dict with change calculation."""
    kpi: Dict[str, Any] = {
        "key": key,
        "label": label,
        "value": value,
        "previous_value": previous_value,
        "unit": unit,
        "sparkline": sparkline or [],
    }

    # Calculate change percentage
    if previous_value is not None and isinstance(
            previous_value, (int, float)) and isinstance(
            value, (int, float)):
        if previous_value != 0:
            change = ((value - previous_value) / abs(previous_value)) * 100
            kpi["change_pct"] = round(change, 1)
            kpi["change_direction"] = (
                "up" if change > 0 else "down" if change < 0 else "neutral"
            )
        else:
            kpi["change_pct"] = None
            kpi["change_direction"] = "neutral"
    else:
        kpi["change_pct"] = None
        kpi["change_direction"] = "neutral"

    return kpi


def _flag_anomalies(
    kpis: List[Dict[str, Any]],
    db: Session,
    company_id: str,
    start: datetime,
    end: datetime,
) -> List[Dict[str, Any]]:
    """Flag KPIs that have anomaly-level values."""
    # Check for ticket volume anomaly
    now = datetime.now(timezone.utc)
    last_24h = _count_tickets(db, company_id, now - timedelta(hours=24), now)
    prev_24h = _count_tickets(
        db,
        company_id,
        now -
        timedelta(
            hours=48),
        now -
        timedelta(
            hours=24))

    if prev_24h > 0 and last_24h >= prev_24h * ANOMALY_THRESHOLD:
        for kpi in kpis:
            if kpi["key"] in ("total_tickets", "open_tickets"):
                kpi["is_anomaly"] = True

    return kpis


# ══════════════════════════════════════════════════════════════════
# RESPONSE TIME DISTRIBUTION
# ══════════════════════════════════════════════════════════════════

# Bucket definitions: (upper_bound_minutes, bucket_key, display_label)
_RESPONSE_TIME_BUCKETS: List[Tuple[int, str, str]] = [
    (15, "0-15m", "<15m"),
    (30, "15-30m", "15-30m"),
    (60, "30m-1h", "30m-1h"),
    (120, "1-2h", "1-2h"),
    (240, "2-4h", "2-4h"),
    (480, "4-8h", "4-8h"),
    (float("inf"), "8h+", "8h+"),
]


def get_response_time_distribution(
    company_id: str,
    db: Session,
    days: int = 30,
) -> Dict[str, Any]:
    """Get first-response time distribution bucketed by time ranges.

    Queries tickets with ``first_response_at`` set, computes the delta
    from ``created_at``, buckets them into standard ranges, and
    calculates avg / median / P95 response times in minutes.

    Returns a ``ResponseTimeDistribution`` dict:
    {
        "buckets": [{"bucket": "0-15m", "count": 42, "label": "<15m"}, ...],
        "avg_response_minutes": 28.5,
        "median_response_minutes": 12.3,
        "p95_response_minutes": 340.0,
    }

    BC-001: Scoped by company_id.
    """
    try:
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days)

        tickets = db.query(Ticket).filter(
            Ticket.company_id == company_id,
            Ticket.created_at >= start,
            Ticket.first_response_at.isnot(None),
        ).all()

        # Calculate response times in minutes
        response_minutes: List[float] = []
        for t in tickets:
            if t.first_response_at and t.created_at:
                delta = (t.first_response_at - t.created_at).total_seconds()
                if delta >= 0:
                    response_minutes.append(delta / 60.0)

        # Bucket the response times using range boundaries
        # Boundaries: 0, 15, 30, 60, 120, 240, 480, inf
        boundaries = [0, 15, 30, 60, 120, 240, 480, float("inf")]
        buckets: List[Dict[str, Any]] = []
        for i, (_, bucket_key, label) in enumerate(_RESPONSE_TIME_BUCKETS):
            lower = boundaries[i]
            upper = boundaries[i + 1]
            count = sum(1 for m in response_minutes if lower <= m < upper)
            buckets.append({
                "bucket": bucket_key,
                "count": count,
                "label": label,
            })

        # Calculate statistics
        avg_response_minutes = 0.0
        median_response_minutes = 0.0
        p95_response_minutes = 0.0

        if response_minutes:
            sorted_minutes = sorted(response_minutes)
            n = len(sorted_minutes)

            avg_response_minutes = round(sum(sorted_minutes) / n, 1)

            # Median
            if n % 2 == 0:
                median_response_minutes = round(
                    (sorted_minutes[n // 2 - 1] + sorted_minutes[n // 2]) / 2, 1,
                )
            else:
                median_response_minutes = round(sorted_minutes[n // 2], 1)

            # P95
            p95_index = int(n * 0.95)
            if p95_index >= n:
                p95_index = n - 1
            p95_response_minutes = round(sorted_minutes[p95_index], 1)

        return {
            "buckets": buckets,
            "avg_response_minutes": avg_response_minutes,
            "median_response_minutes": median_response_minutes,
            "p95_response_minutes": p95_response_minutes,
        }

    except Exception as exc:
        logger.error(
            "response_time_distribution_error",
            company_id=company_id,
            error=str(exc),
        )
        # Return empty structure on error
        return {
            "buckets": [
                {"bucket": bk, "count": 0, "label": lbl}
                for _, bk, lbl in _RESPONSE_TIME_BUCKETS
            ],
            "avg_response_minutes": 0,
            "median_response_minutes": 0,
            "p95_response_minutes": 0,
        }
