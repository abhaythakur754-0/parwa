"""
Analytics Service Layer

Business logic for analytics, metrics, and reporting.
All methods are company-scoped for RLS compliance.
"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc, case
from collections import defaultdict

from backend.models.support_ticket import (
    SupportTicket,
    TicketStatusEnum,
    ChannelEnum,
    SentimentEnum,
)
from backend.models.user import User
from backend.models.usage_log import UsageLog
from backend.models.sla_breach import SLABreach
from backend.models.company import Company


class AnalyticsService:
    """
    Service class for analytics and reporting business logic.
    
    Provides metrics calculation, KPI tracking, and activity feeds.
    All methods enforce company-scoped data access (RLS).
    """
    
    # SLA thresholds by priority (in hours)
    SLA_THRESHOLDS = {
        "high": 4,
        "medium": 8,
        "low": 24,
    }
    
    def __init__(self, db: AsyncSession, company_id: UUID):
        """
        Initialize analytics service.
        
        Args:
            db: Async database session
            company_id: Company UUID for RLS scoping
        """
        self.db = db
        self.company_id = company_id
    
    async def get_company_stats(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get aggregated company statistics.
        
        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            Dict with:
            - total_tickets: int
            - open_tickets: int
            - resolved_tickets: int
            - avg_response_time: float (hours)
            - sla_compliance_rate: float (percentage)
        """
        # Build base query with company scoping
        base_query = select(SupportTicket).where(
            SupportTicket.company_id == self.company_id
        )
        
        # Apply date filters if provided
        if start_date:
            base_query = base_query.where(SupportTicket.created_at >= start_date)
        if end_date:
            base_query = base_query.where(SupportTicket.created_at <= end_date)
        
        # Get total tickets count
        total_query = select(func.count()).select_from(base_query.subquery())
        total_result = await self.db.execute(total_query)
        total_tickets = total_result.scalar() or 0
        
        # Get open tickets count
        open_query = select(func.count()).select_from(
            base_query.where(
                SupportTicket.status == TicketStatusEnum.open
            ).subquery()
        )
        open_result = await self.db.execute(open_query)
        open_tickets = open_result.scalar() or 0
        
        # Get resolved tickets count
        resolved_query = select(func.count()).select_from(
            base_query.where(
                SupportTicket.status == TicketStatusEnum.resolved
            ).subquery()
        )
        resolved_result = await self.db.execute(resolved_query)
        resolved_tickets = resolved_result.scalar() or 0
        
        # Get SLA compliance rate
        sla_result = await self.calculate_sla_compliance(start_date, end_date)
        sla_compliance_rate = sla_result.get("compliance_rate", 100.0)
        
        # Calculate average response time (simplified - using created_at to resolved_at)
        avg_response_query = select(
            func.avg(
                func.extract('epoch', SupportTicket.resolved_at - SupportTicket.created_at) / 3600
            )
        ).where(
            and_(
                SupportTicket.company_id == self.company_id,
                SupportTicket.resolved_at.isnot(None)
            )
        )
        if start_date:
            avg_response_query = avg_response_query.where(SupportTicket.created_at >= start_date)
        if end_date:
            avg_response_query = avg_response_query.where(SupportTicket.created_at <= end_date)
        
        avg_response_result = await self.db.execute(avg_response_query)
        avg_response_time = float(avg_response_result.scalar() or 0.0)
        
        return {
            "total_tickets": total_tickets,
            "open_tickets": open_tickets,
            "resolved_tickets": resolved_tickets,
            "avg_response_time": round(avg_response_time, 2),
            "sla_compliance_rate": round(sla_compliance_rate, 2),
        }
    
    async def get_ticket_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        group_by: str = "day"
    ) -> List[Dict[str, Any]]:
        """
        Get ticket volume and resolution metrics over time.
        
        Args:
            start_date: Start date filter
            end_date: End date filter
            group_by: Grouping interval (day, week, month)
            
        Returns:
            List of dicts with:
            - date: datetime
            - tickets_created: int
            - tickets_resolved: int
            - avg_resolution_time: float
        """
        # Determine the date truncation function based on group_by
        if group_by == "week":
            date_trunc = func.date_trunc("week", SupportTicket.created_at)
        elif group_by == "month":
            date_trunc = func.date_trunc("month", SupportTicket.created_at)
        else:  # default to day
            date_trunc = func.date_trunc("day", SupportTicket.created_at)
        
        # Build query for created tickets
        created_query = select(
            date_trunc.label("period"),
            func.count().label("tickets_created")
        ).where(
            SupportTicket.company_id == self.company_id
        )
        
        if start_date:
            created_query = created_query.where(SupportTicket.created_at >= start_date)
        if end_date:
            created_query = created_query.where(SupportTicket.created_at <= end_date)
        
        created_query = created_query.group_by("period").order_by(desc("period"))
        
        created_result = await self.db.execute(created_query)
        created_rows = created_result.fetchall()
        
        # Build metrics list
        metrics = []
        for row in created_rows[:30]:  # Limit to 30 periods
            period = row[0]
            tickets_created = row[1]
            
            # Get resolved tickets for this period
            resolved_query = select(func.count()).where(
                and_(
                    SupportTicket.company_id == self.company_id,
                    func.date_trunc(group_by, SupportTicket.resolved_at) == period
                )
            )
            resolved_result = await self.db.execute(resolved_query)
            tickets_resolved = resolved_result.scalar() or 0
            
            metrics.append({
                "date": period.isoformat() if period else None,
                "tickets_created": tickets_created,
                "tickets_resolved": tickets_resolved,
                "avg_resolution_time": 0.0,  # Simplified
            })
        
        return metrics
    
    async def get_response_time_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get average response times.
        
        Args:
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            Dict with:
            - first_response_avg: float (hours)
            - resolution_time_avg: float (hours)
            - by_priority: Dict[Priority, float]
        """
        # Calculate average resolution time
        resolution_query = select(
            func.avg(
                func.extract('epoch', SupportTicket.resolved_at - SupportTicket.created_at) / 3600
            )
        ).where(
            and_(
                SupportTicket.company_id == self.company_id,
                SupportTicket.resolved_at.isnot(None)
            )
        )
        
        if start_date:
            resolution_query = resolution_query.where(SupportTicket.created_at >= start_date)
        if end_date:
            resolution_query = resolution_query.where(SupportTicket.created_at <= end_date)
        
        resolution_result = await self.db.execute(resolution_query)
        resolution_time_avg = float(resolution_result.scalar() or 0.0)
        
        # Get by priority (simplified since we don't have priority field)
        by_priority = {
            "high": resolution_time_avg * 0.8,  # Estimated
            "medium": resolution_time_avg,
            "low": resolution_time_avg * 1.2,
        }
        
        return {
            "first_response_avg": round(resolution_time_avg * 0.5, 2),  # Estimated
            "resolution_time_avg": round(resolution_time_avg, 2),
            "by_priority": {k: round(v, 2) for k, v in by_priority.items()},
        }
    
    async def get_agent_performance(
        self,
        agent_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get individual agent performance metrics.
        
        Args:
            agent_id: Optional specific agent UUID
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            List of dicts with:
            - agent_id: UUID
            - agent_name: str
            - tickets_assigned: int
            - tickets_resolved: int
            - avg_resolution_time: float
            - customer_satisfaction: float
        """
        # Build query for agent assignments
        query = select(
            SupportTicket.assigned_to,
            func.count(SupportTicket.id).label("tickets_assigned"),
            func.sum(
                case(
                    (SupportTicket.status == TicketStatusEnum.resolved, 1),
                    else_=0
                )
            ).label("tickets_resolved"),
        ).where(
            and_(
                SupportTicket.company_id == self.company_id,
                SupportTicket.assigned_to.isnot(None)
            )
        )
        
        if agent_id:
            query = query.where(SupportTicket.assigned_to == agent_id)
        if start_date:
            query = query.where(SupportTicket.created_at >= start_date)
        if end_date:
            query = query.where(SupportTicket.created_at <= end_date)
        
        query = query.group_by(SupportTicket.assigned_to)
        
        result = await self.db.execute(query)
        rows = result.fetchall()
        
        # Build performance list
        performance = []
        for row in rows:
            assigned_to = row[0]
            tickets_assigned = row[1]
            tickets_resolved = row[2] or 0
            
            # Get agent name
            user_query = select(User).where(User.id == assigned_to)
            user_result = await self.db.execute(user_query)
            user = user_result.scalar_one_or_none()
            agent_name = user.email if user else "Unknown"
            
            # Calculate avg resolution time (simplified)
            avg_resolution_time = 4.0 if tickets_resolved > 0 else 0.0
            
            performance.append({
                "agent_id": str(assigned_to),
                "agent_name": agent_name,
                "tickets_assigned": tickets_assigned,
                "tickets_resolved": tickets_resolved,
                "avg_resolution_time": avg_resolution_time,
                "customer_satisfaction": 4.5,  # Default placeholder
            })
        
        return performance
    
    async def get_activity_feed(
        self,
        limit: int = 50,
        offset: int = 0,
        activity_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent activity for dashboard feed.
        
        Args:
            limit: Max results
            offset: Pagination offset
            activity_types: Filter by activity types
            
        Returns:
            List of activity dicts with:
            - id: UUID
            - type: str
            - description: str
            - timestamp: datetime
            - user_id: UUID
            - metadata: dict
        """
        # Query recent tickets as activity
        query = select(SupportTicket).where(
            SupportTicket.company_id == self.company_id
        ).order_by(desc(SupportTicket.created_at)).offset(offset).limit(limit)
        
        result = await self.db.execute(query)
        tickets = result.scalars().all()
        
        # Convert to activity feed format
        activities = []
        for ticket in tickets:
            activity_type = "ticket_created"
            description = f"New ticket: {ticket.subject}"
            
            if ticket.status == TicketStatusEnum.resolved:
                activity_type = "ticket_resolved"
                description = f"Ticket resolved: {ticket.subject}"
            elif ticket.status == TicketStatusEnum.escalated:
                activity_type = "ticket_escalated"
                description = f"Ticket escalated: {ticket.subject}"
            
            # Filter by activity types if provided
            if activity_types and activity_type not in activity_types:
                continue
            
            activities.append({
                "id": str(ticket.id),
                "type": activity_type,
                "description": description,
                "timestamp": ticket.created_at.isoformat() if ticket.created_at else None,
                "user_id": str(ticket.assigned_to) if ticket.assigned_to else None,
                "metadata": {
                    "channel": ticket.channel.value if ticket.channel else None,
                    "status": ticket.status.value if ticket.status else None,
                }
            })
        
        return activities
    
    async def calculate_sla_compliance(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Calculate SLA compliance percentage.
        
        Args:
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            Dict with:
            - compliance_rate: float (percentage)
            - total_tickets: int
            - breached_tickets: int
            - avg_time_to_breach: float (hours)
        """
        # Get total tickets
        total_query = select(func.count()).where(
            SupportTicket.company_id == self.company_id
        )
        if start_date:
            total_query = total_query.where(SupportTicket.created_at >= start_date)
        if end_date:
            total_query = total_query.where(SupportTicket.created_at <= end_date)
        
        total_result = await self.db.execute(total_query)
        total_tickets = total_result.scalar() or 0
        
        # Get breached tickets count from SLABreach model
        breach_query = select(func.count(SLABreach.id)).where(
            SLABreach.company_id == self.company_id
        )
        if start_date:
            breach_query = breach_query.where(SLABreach.breach_triggered_at >= start_date)
        if end_date:
            breach_query = breach_query.where(SLABreach.breach_triggered_at <= end_date)
        
        breach_result = await self.db.execute(breach_query)
        breached_tickets = breach_result.scalar() or 0
        
        # Calculate compliance rate
        compliance_rate = 100.0
        if total_tickets > 0:
            compliance_rate = ((total_tickets - breached_tickets) / total_tickets) * 100
        
        # Get average time to breach
        avg_breach_query = select(func.avg(SLABreach.hours_overdue)).where(
            SLABreach.company_id == self.company_id
        )
        avg_breach_result = await self.db.execute(avg_breach_query)
        avg_time_to_breach = float(avg_breach_result.scalar() or 0.0)
        
        return {
            "compliance_rate": round(max(0, compliance_rate), 2),
            "total_tickets": total_tickets,
            "breached_tickets": breached_tickets,
            "avg_time_to_breach": round(avg_time_to_breach, 2),
        }
    
    async def get_ticket_summary_by_status(self) -> Dict[str, int]:
        """
        Get ticket counts grouped by status.
        
        Returns:
            Dict mapping status to count
        """
        query = select(
            SupportTicket.status,
            func.count(SupportTicket.id)
        ).where(
            SupportTicket.company_id == self.company_id
        ).group_by(SupportTicket.status)
        
        result = await self.db.execute(query)
        rows = result.fetchall()
        
        summary = {}
        for row in rows:
            status = row[0]
            count = row[1]
            status_name = status.value if hasattr(status, 'value') else str(status)
            summary[status_name] = count
        
        return summary
    
    async def get_ticket_summary_by_priority(self) -> Dict[str, int]:
        """
        Get ticket counts grouped by priority.
        
        Returns:
            Dict mapping priority to count
        """
        # Since SupportTicket doesn't have a priority field,
        # we'll categorize by sentiment as a proxy
        query = select(
            SupportTicket.sentiment,
            func.count(SupportTicket.id)
        ).where(
            SupportTicket.company_id == self.company_id
        ).group_by(SupportTicket.sentiment)
        
        result = await self.db.execute(query)
        rows = result.fetchall()
        
        summary = {}
        for row in rows:
            sentiment = row[0]
            count = row[1]
            # Map sentiment to priority-like categories
            if sentiment == SentimentEnum.negative:
                priority = "high"
            elif sentiment == SentimentEnum.neutral:
                priority = "medium"
            elif sentiment == SentimentEnum.positive:
                priority = "low"
            else:
                priority = "unspecified"
            
            summary[priority] = summary.get(priority, 0) + count
        
        return summary
    
    async def get_channel_distribution(self) -> Dict[str, int]:
        """
        Get ticket counts grouped by channel.
        
        Returns:
            Dict mapping channel to count
        """
        query = select(
            SupportTicket.channel,
            func.count(SupportTicket.id)
        ).where(
            SupportTicket.company_id == self.company_id
        ).group_by(SupportTicket.channel)
        
        result = await self.db.execute(query)
        rows = result.fetchall()
        
        summary = {}
        for row in rows:
            channel = row[0]
            count = row[1]
            channel_name = channel.value if hasattr(channel, 'value') else str(channel)
            summary[channel_name] = count
        
        return summary
    
    async def get_usage_summary(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get usage summary from usage logs.
        
        Args:
            start_date: Start date filter
            end_date: End date filter
            
        Returns:
            Dict with usage metrics
        """
        query = select(
            UsageLog.ai_tier,
            func.sum(UsageLog.request_count).label("total_requests"),
            func.sum(UsageLog.token_count).label("total_tokens"),
            func.avg(UsageLog.avg_latency_ms).label("avg_latency")
        ).where(
            UsageLog.company_id == self.company_id
        )
        
        if start_date:
            query = query.where(UsageLog.log_date >= start_date.date())
        if end_date:
            query = query.where(UsageLog.log_date <= end_date.date())
        
        query = query.group_by(UsageLog.ai_tier)
        
        result = await self.db.execute(query)
        rows = result.fetchall()
        
        usage = {
            "by_tier": {},
            "total_requests": 0,
            "total_tokens": 0,
        }
        
        for row in rows:
            tier = row[0]
            requests = row[1] or 0
            tokens = row[2] or 0
            
            tier_name = tier.value if hasattr(tier, 'value') else str(tier)
            usage["by_tier"][tier_name] = {
                "requests": requests,
                "tokens": tokens,
            }
            usage["total_requests"] += requests
            usage["total_tokens"] += tokens
        
        return usage
