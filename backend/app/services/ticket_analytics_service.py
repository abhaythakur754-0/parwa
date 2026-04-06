"""
PARWA Ticket Analytics Service (MF10)

Provides ticket analytics and reporting capabilities:
- get_summary: Total tickets, by status, by priority
- get_trends: Ticket volume over time
- get_category_distribution: Distribution by category
- get_sla_metrics: SLA compliance, avg response/resolution time
- get_agent_metrics: Per-agent metrics

BC-001: All queries are tenant-scoped via company_id.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session

from database.models.tickets import (
    Ticket,
    TicketMessage,
    TicketFeedback,
    TicketStatus,
    TicketPriority,
    TicketCategory,
    SLATimer,
    TicketAssignment,
)
from backend.app.logger import get_logger

logger = get_logger("ticket_analytics")


class IntervalType(str, Enum):
    """Time interval types for trend analysis."""
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


@dataclass
class DateRange:
    """Date range filter for analytics queries."""
    start_date: datetime
    end_date: datetime

    @classmethod
    def last_n_days(cls, n: int) -> "DateRange":
        """Create a date range for the last N days."""
        end = datetime.utcnow()
        start = end - timedelta(days=n)
        return cls(start_date=start, end_date=end)

    @classmethod
    def last_n_hours(cls, n: int) -> "DateRange":
        """Create a date range for the last N hours."""
        end = datetime.utcnow()
        start = end - timedelta(hours=n)
        return cls(start_date=start, end_date=end)

    @classmethod
    def last_n_weeks(cls, n: int) -> "DateRange":
        """Create a date range for the last N weeks."""
        end = datetime.utcnow()
        start = end - timedelta(weeks=n)
        return cls(start_date=start, end_date=end)

    @classmethod
    def last_n_months(cls, n: int) -> "DateRange":
        """Create a date range for the last N months (approximate)."""
        end = datetime.utcnow()
        start = end - timedelta(days=n * 30)
        return cls(start_date=start, end_date=end)


@dataclass
class TicketSummary:
    """Summary statistics for tickets."""
    total_tickets: int = 0
    open_tickets: int = 0
    in_progress_tickets: int = 0
    resolved_tickets: int = 0
    closed_tickets: int = 0
    awaiting_client_tickets: int = 0
    awaiting_human_tickets: int = 0
    
    # Priority breakdown
    critical_tickets: int = 0
    high_tickets: int = 0
    medium_tickets: int = 0
    low_tickets: int = 0
    
    # Rates
    resolution_rate: float = 0.0
    avg_resolution_time_hours: Optional[float] = None
    avg_first_response_time_hours: Optional[float] = None
    
    # Date range
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


@dataclass
class TrendPoint:
    """A single point in a trend series."""
    timestamp: datetime
    count: int
    label: str


@dataclass
class CategoryDistribution:
    """Category distribution data."""
    category: str
    count: int
    percentage: float


@dataclass
class SLAMetrics:
    """SLA performance metrics."""
    total_tickets_with_sla: int = 0
    breached_count: int = 0
    approaching_count: int = 0
    compliant_count: int = 0
    compliance_rate: float = 1.0
    avg_first_response_minutes: Optional[float] = None
    avg_resolution_minutes: Optional[float] = None
    avg_update_frequency_minutes: Optional[float] = None


@dataclass
class AgentMetrics:
    """Per-agent performance metrics."""
    agent_id: str
    agent_name: Optional[str] = None
    tickets_assigned: int = 0
    tickets_resolved: int = 0
    tickets_open: int = 0
    avg_resolution_time_hours: Optional[float] = None
    avg_first_response_time_hours: Optional[float] = None
    csat_avg: Optional[float] = None
    csat_count: int = 0
    resolution_rate: float = 0.0


class TicketAnalyticsService:
    """Service for ticket analytics queries (MF10)."""

    def __init__(self, db: Session, company_id: str):
        self.db = db
        self.company_id = company_id

    def get_summary(self, date_range: Optional[DateRange] = None) -> TicketSummary:
        """Get summary statistics for tickets.

        Args:
            date_range: Optional date range filter

        Returns:
            TicketSummary with counts and rates
        """
        query = self.db.query(Ticket).filter(
            Ticket.company_id == self.company_id
        )

        if date_range:
            query = query.filter(
                Ticket.created_at >= date_range.start_date,
                Ticket.created_at <= date_range.end_date,
            )

        # Get all tickets
        tickets = query.all()

        # Count by status
        status_counts = {}
        for status in TicketStatus:
            status_counts[status.value] = 0

        for ticket in tickets:
            status_counts[ticket.status] = status_counts.get(ticket.status, 0) + 1

        # Count by priority
        priority_counts = {}
        for priority in TicketPriority:
            priority_counts[priority.value] = 0

        for ticket in tickets:
            priority_counts[ticket.priority] = priority_counts.get(ticket.priority, 0) + 1

        total = len(tickets)
        resolved_count = status_counts.get(TicketStatus.resolved.value, 0)
        closed_count = status_counts.get(TicketStatus.closed.value, 0)

        # Calculate resolution rate
        resolution_rate = 0.0
        if total > 0:
            resolution_rate = (resolved_count + closed_count) / total

        # Calculate average times
        avg_resolution_time = self._calculate_avg_resolution_time(tickets)
        avg_first_response = self._calculate_avg_first_response_time(tickets)

        return TicketSummary(
            total_tickets=total,
            open_tickets=status_counts.get(TicketStatus.open.value, 0),
            in_progress_tickets=status_counts.get(TicketStatus.in_progress.value, 0),
            resolved_tickets=resolved_count,
            closed_tickets=closed_count,
            awaiting_client_tickets=status_counts.get(TicketStatus.awaiting_client.value, 0),
            awaiting_human_tickets=status_counts.get(TicketStatus.awaiting_human.value, 0),
            critical_tickets=priority_counts.get(TicketPriority.critical.value, 0),
            high_tickets=priority_counts.get(TicketPriority.high.value, 0),
            medium_tickets=priority_counts.get(TicketPriority.medium.value, 0),
            low_tickets=priority_counts.get(TicketPriority.low.value, 0),
            resolution_rate=resolution_rate,
            avg_resolution_time_hours=avg_resolution_time,
            avg_first_response_time_hours=avg_first_response,
            start_date=date_range.start_date if date_range else None,
            end_date=date_range.end_date if date_range else None,
        )

    def get_trends(
        self,
        interval: IntervalType,
        date_range: Optional[DateRange] = None,
    ) -> List[TrendPoint]:
        """Get ticket volume trends over time.

        Args:
            interval: Time interval (hour, day, week, month)
            date_range: Optional date range filter

        Returns:
            List of TrendPoint objects
        """
        if date_range is None:
            date_range = DateRange.last_n_days(30)

        query = self.db.query(Ticket).filter(
            Ticket.company_id == self.company_id,
            Ticket.created_at >= date_range.start_date,
            Ticket.created_at <= date_range.end_date,
        )

        tickets = query.order_by(Ticket.created_at).all()

        # Group tickets by interval
        groups: Dict[str, int] = {}
        time_format = self._get_time_format(interval)

        for ticket in tickets:
            if ticket.created_at:
                key = ticket.created_at.strftime(time_format)
                groups[key] = groups.get(key, 0) + 1

        # Generate trend points
        trends = []
        current = date_range.start_date

        while current <= date_range.end_date:
            key = current.strftime(time_format)
            label = self._format_label(current, interval)

            trends.append(TrendPoint(
                timestamp=current,
                count=groups.get(key, 0),
                label=label,
            ))

            current = self._increment_by_interval(current, interval)

        return trends

    def get_category_distribution(
        self,
        date_range: Optional[DateRange] = None,
    ) -> List[CategoryDistribution]:
        """Get distribution of tickets by category.

        Args:
            date_range: Optional date range filter

        Returns:
            List of CategoryDistribution objects
        """
        query = self.db.query(Ticket).filter(
            Ticket.company_id == self.company_id
        )

        if date_range:
            query = query.filter(
                Ticket.created_at >= date_range.start_date,
                Ticket.created_at <= date_range.end_date,
            )

        # Group by category
        result = query.with_entities(
            Ticket.category,
            func.count(Ticket.id).label("count"),
        ).group_by(Ticket.category).all()

        total = sum(row.count for row in result if row.category)

        distributions = []
        for row in result:
            if row.category:
                percentage = (row.count / total * 100) if total > 0 else 0
                distributions.append(CategoryDistribution(
                    category=row.category,
                    count=row.count,
                    percentage=round(percentage, 1),
                ))

        # Sort by count descending
        distributions.sort(key=lambda x: x.count, reverse=True)

        return distributions

    def get_sla_metrics(
        self,
        date_range: Optional[DateRange] = None,
    ) -> SLAMetrics:
        """Get SLA performance metrics.

        Args:
            date_range: Optional date range filter

        Returns:
            SLAMetrics with compliance and timing data
        """
        query = self.db.query(SLATimer).filter(
            SLATimer.company_id == self.company_id
        )

        if date_range:
            query = query.filter(
                SLATimer.created_at >= date_range.start_date,
                SLATimer.created_at <= date_range.end_date,
            )

        timers = query.all()

        if not timers:
            return SLAMetrics()

        breached = [t for t in timers if t.is_breached]
        compliant = [t for t in timers if not t.is_breached and t.resolved_at]

        total = len(timers)
        breached_count = len(breached)
        compliant_count = len(compliant)

        # Calculate averages
        first_response_times = []
        for t in timers:
            if t.first_response_at and t.created_at:
                minutes = (t.first_response_at - t.created_at).total_seconds() / 60
                first_response_times.append(minutes)

        resolution_times = []
        for t in timers:
            if t.resolved_at and t.created_at:
                minutes = (t.resolved_at - t.created_at).total_seconds() / 60
                resolution_times.append(minutes)

        # Count approaching (would need more complex calculation)
        approaching_count = 0  # Placeholder - would need real-time calculation

        return SLAMetrics(
            total_tickets_with_sla=total,
            breached_count=breached_count,
            approaching_count=approaching_count,
            compliant_count=compliant_count,
            compliance_rate=1.0 - (breached_count / total) if total > 0 else 1.0,
            avg_first_response_minutes=(
                sum(first_response_times) / len(first_response_times)
                if first_response_times else None
            ),
            avg_resolution_minutes=(
                sum(resolution_times) / len(resolution_times)
                if resolution_times else None
            ),
        )

    def get_agent_metrics(
        self,
        date_range: Optional[DateRange] = None,
    ) -> List[AgentMetrics]:
        """Get per-agent performance metrics.

        Args:
            date_range: Optional date range filter

        Returns:
            List of AgentMetrics objects
        """
        from database.models.core import User

        # Get all assignments in date range
        assignment_query = self.db.query(TicketAssignment).filter(
            TicketAssignment.company_id == self.company_id,
        )

        if date_range:
            assignment_query = assignment_query.filter(
                TicketAssignment.assigned_at >= date_range.start_date,
                TicketAssignment.assigned_at <= date_range.end_date,
            )

        assignments = assignment_query.all()

        # Group by assignee
        agent_data: Dict[str, Dict[str, Any]] = {}

        for assignment in assignments:
            agent_id = assignment.assignee_id
            if not agent_id:
                continue

            if agent_id not in agent_data:
                agent_data[agent_id] = {
                    "tickets_assigned": 0,
                    "resolved": set(),
                    "open": set(),
                }

            agent_data[agent_id]["tickets_assigned"] += 1

        # Get ticket status per agent
        tickets_query = self.db.query(Ticket).filter(
            Ticket.company_id == self.company_id,
            Ticket.assigned_to.in_(agent_data.keys()),
        )

        if date_range:
            tickets_query = tickets_query.filter(
                Ticket.created_at >= date_range.start_date,
                Ticket.created_at <= date_range.end_date,
            )

        tickets = tickets_query.all()

        for ticket in tickets:
            agent_id = ticket.assigned_to
            if not agent_id or agent_id not in agent_data:
                continue

            if ticket.status in [TicketStatus.resolved.value, TicketStatus.closed.value]:
                agent_data[agent_id]["resolved"].add(ticket.id)
            else:
                agent_data[agent_id]["open"].add(ticket.id)

        # Get CSAT data
        csat_query = self.db.query(
            Ticket.assigned_to,
            func.avg(TicketFeedback.rating).label("avg_rating"),
            func.count(TicketFeedback.id).label("count"),
        ).join(
            TicketFeedback, Ticket.id == TicketFeedback.ticket_id
        ).filter(
            Ticket.company_id == self.company_id,
            Ticket.assigned_to.in_(agent_data.keys()),
        ).group_by(Ticket.assigned_to)

        if date_range:
            csat_query = csat_query.filter(
                TicketFeedback.created_at >= date_range.start_date,
                TicketFeedback.created_at <= date_range.end_date,
            )

        csat_data = {row.assigned_to: (row.avg_rating, row.count) for row in csat_query.all()}

        # Get user names
        user_ids = list(agent_data.keys())
        users = self.db.query(User).filter(User.id.in_(user_ids)).all()
        user_names = {u.id: u.name for u in users}

        # Build metrics list
        metrics = []
        for agent_id, data in agent_data.items():
            resolved_count = len(data["resolved"])
            open_count = len(data["open"])
            assigned = data["tickets_assigned"]

            resolution_rate = resolved_count / assigned if assigned > 0 else 0

            csat_avg, csat_count = csat_data.get(agent_id, (None, 0))

            metrics.append(AgentMetrics(
                agent_id=agent_id,
                agent_name=user_names.get(agent_id),
                tickets_assigned=assigned,
                tickets_resolved=resolved_count,
                tickets_open=open_count,
                resolution_rate=resolution_rate,
                csat_avg=round(float(csat_avg), 2) if csat_avg else None,
                csat_count=csat_count,
            ))

        # Sort by tickets resolved descending
        metrics.sort(key=lambda x: x.tickets_resolved, reverse=True)

        return metrics

    # ── Helper Methods ─────────────────────────────────────────────────────

    def _calculate_avg_resolution_time(self, tickets: List[Ticket]) -> Optional[float]:
        """Calculate average resolution time in hours."""
        times = []
        for ticket in tickets:
            if ticket.closed_at and ticket.created_at:
                hours = (ticket.closed_at - ticket.created_at).total_seconds() / 3600
                times.append(hours)

        return sum(times) / len(times) if times else None

    def _calculate_avg_first_response_time(self, tickets: List[Ticket]) -> Optional[float]:
        """Calculate average first response time in hours."""
        times = []
        for ticket in tickets:
            if ticket.first_response_at and ticket.created_at:
                hours = (ticket.first_response_at - ticket.created_at).total_seconds() / 3600
                times.append(hours)

        return sum(times) / len(times) if times else None

    def _get_time_format(self, interval: IntervalType) -> str:
        """Get strftime format for interval."""
        formats = {
            IntervalType.HOUR: "%Y-%m-%d %H:00",
            IntervalType.DAY: "%Y-%m-%d",
            IntervalType.WEEK: "%Y-%W",
            IntervalType.MONTH: "%Y-%m",
        }
        return formats[interval]

    def _format_label(self, dt: datetime, interval: IntervalType) -> str:
        """Format a label for the trend point."""
        labels = {
            IntervalType.HOUR: dt.strftime("%H:00"),
            IntervalType.DAY: dt.strftime("%b %d"),
            IntervalType.WEEK: f"Week {dt.isocalendar()[1]}",
            IntervalType.MONTH: dt.strftime("%b %Y"),
        }
        return labels[interval]

    def _increment_by_interval(self, dt: datetime, interval: IntervalType) -> datetime:
        """Increment datetime by interval."""
        deltas = {
            IntervalType.HOUR: timedelta(hours=1),
            IntervalType.DAY: timedelta(days=1),
            IntervalType.WEEK: timedelta(weeks=1),
            IntervalType.MONTH: timedelta(days=30),  # Approximate
        }
        return dt + deltas[interval]
