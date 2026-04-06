"""
PARWA SLA (Service Level Agreement) Service

Handles SLA policy management and enforcement.
- SLA policy CRUD operations
- SLA timer creation and tracking
- Breach detection and notification
- SLA statistics

Day 29 - MF06, PS11, PS17 implementation.

Default SLA policies by plan tier:
- Starter: critical 1h/8h, high 4h/24h, medium 12h/48h, low 24h/72h
- Growth: Half of Starter times
- High: Half of Growth times
"""

from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Dict, Any
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from database.models.tickets import (
    SLAPolicy,
    SLATimer,
    Ticket,
    TicketPriority,
    TicketStatus,
)
from backend.app.schemas.sla import Priority, PlanTier, BreachType


class SLAError(Exception):
    """Base exception for SLA operations."""
    pass


class SLAPolicyNotFoundError(SLAError):
    """Raised when SLA policy is not found."""
    pass


class SLATimerNotFoundError(SLAError):
    """Raised when SLA timer is not found."""
    pass


class DuplicateSLAPolicyError(SLAError):
    """Raised when a duplicate SLA policy would be created."""
    pass


class SLAService:
    """Service for SLA policy management and timer enforcement."""

    # Default SLA policies (minutes) - plan_tier × priority
    # Format: (first_response_minutes, resolution_minutes, update_frequency_minutes)
    DEFAULT_POLICIES = {
        PlanTier.starter.value: {
            Priority.critical.value: (60, 480, 30),      # 1h first response, 8h resolution
            Priority.high.value: (240, 1440, 60),        # 4h first response, 24h resolution
            Priority.medium.value: (720, 2880, 120),     # 12h first response, 48h resolution
            Priority.low.value: (1440, 4320, 240),       # 24h first response, 72h resolution
        },
        PlanTier.growth.value: {
            Priority.critical.value: (30, 240, 15),      # Half of starter
            Priority.high.value: (120, 720, 30),
            Priority.medium.value: (360, 1440, 60),
            Priority.low.value: (720, 2160, 120),
        },
        PlanTier.high.value: {
            Priority.critical.value: (15, 120, 10),      # Half of growth
            Priority.high.value: (60, 360, 15),
            Priority.medium.value: (180, 720, 30),
            Priority.low.value: (360, 1080, 60),
        },
    }

    # SLA approaching threshold (percentage)
    APPROACHING_THRESHOLD = 0.75  # 75%

    def __init__(self, db: Session):
        self.db = db

    # ── SLA Policy CRUD ─────────────────────────────────────────────────────

    def create_policy(
        self,
        company_id: str,
        plan_tier: str,
        priority: str,
        first_response_minutes: int,
        resolution_minutes: int,
        update_frequency_minutes: int,
        is_active: bool = True,
    ) -> SLAPolicy:
        """
        Create a new SLA policy.
        
        Raises:
            DuplicateSLAPolicyError: If policy already exists for this plan_tier × priority
        """
        # Check for duplicate
        existing = self.db.query(SLAPolicy).filter(
            SLAPolicy.company_id == company_id,
            SLAPolicy.plan_tier == plan_tier,
            SLAPolicy.priority == priority,
        ).first()
        
        if existing:
            raise DuplicateSLAPolicyError(
                f"SLA policy already exists for {plan_tier}/{priority}"
            )
        
        policy = SLAPolicy(
            company_id=company_id,
            plan_tier=plan_tier,
            priority=priority,
            first_response_minutes=first_response_minutes,
            resolution_minutes=resolution_minutes,
            update_frequency_minutes=update_frequency_minutes,
            is_active=is_active,
        )
        self.db.add(policy)
        self.db.commit()
        
        return policy

    def get_policy(
        self,
        company_id: str,
        policy_id: str,
    ) -> Optional[SLAPolicy]:
        """Get an SLA policy by ID."""
        return self.db.query(SLAPolicy).filter(
            SLAPolicy.id == policy_id,
            SLAPolicy.company_id == company_id,
        ).first()

    def get_policy_by_tier_priority(
        self,
        company_id: str,
        plan_tier: str,
        priority: str,
    ) -> Optional[SLAPolicy]:
        """Get SLA policy for a specific plan tier and priority."""
        return self.db.query(SLAPolicy).filter(
            SLAPolicy.company_id == company_id,
            SLAPolicy.plan_tier == plan_tier,
            SLAPolicy.priority == priority,
            SLAPolicy.is_active == True,  # noqa: E712
        ).first()

    def list_policies(
        self,
        company_id: str,
        plan_tier: Optional[str] = None,
        priority: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> List[SLAPolicy]:
        """List SLA policies with optional filters."""
        query = self.db.query(SLAPolicy).filter(
            SLAPolicy.company_id == company_id,
        )
        
        if plan_tier:
            query = query.filter(SLAPolicy.plan_tier == plan_tier)
        if priority:
            query = query.filter(SLAPolicy.priority == priority)
        if is_active is not None:
            query = query.filter(SLAPolicy.is_active == is_active)
        
        return query.order_by(SLAPolicy.plan_tier, SLAPolicy.priority).all()

    def update_policy(
        self,
        company_id: str,
        policy_id: str,
        **kwargs,
    ) -> SLAPolicy:
        """Update an SLA policy."""
        policy = self.get_policy(company_id, policy_id)
        
        if not policy:
            raise SLAPolicyNotFoundError(f"SLA policy {policy_id} not found")
        
        # Update allowed fields
        allowed_fields = [
            "first_response_minutes",
            "resolution_minutes",
            "update_frequency_minutes",
            "is_active",
        ]
        
        for field in allowed_fields:
            if field in kwargs:
                setattr(policy, field, kwargs[field])
        
        policy.updated_at = datetime.utcnow()
        self.db.commit()
        
        return policy

    def delete_policy(
        self,
        company_id: str,
        policy_id: str,
    ) -> bool:
        """Delete an SLA policy."""
        policy = self.get_policy(company_id, policy_id)
        
        if not policy:
            raise SLAPolicyNotFoundError(f"SLA policy {policy_id} not found")
        
        self.db.delete(policy)
        self.db.commit()
        
        return True

    def seed_default_policies(
        self,
        company_id: str,
        plan_tier: Optional[str] = None,
    ) -> List[SLAPolicy]:
        """
        Seed default SLA policies for a company.
        
        Args:
            company_id: Company to seed policies for
            plan_tier: Optional specific tier to seed (default: all tiers)
            
        Returns:
            List of created policies
        """
        created_policies = []
        
        tiers_to_seed = [plan_tier] if plan_tier else list(self.DEFAULT_POLICIES.keys())
        
        for tier in tiers_to_seed:
            if tier not in self.DEFAULT_POLICIES:
                continue
                
            for priority, (first_resp, resolution, update_freq) in self.DEFAULT_POLICIES[tier].items():
                # Check if already exists
                existing = self.get_policy_by_tier_priority(company_id, tier, priority)
                if existing:
                    continue
                
                policy = self.create_policy(
                    company_id=company_id,
                    plan_tier=tier,
                    priority=priority,
                    first_response_minutes=first_resp,
                    resolution_minutes=resolution,
                    update_frequency_minutes=update_freq,
                    is_active=True,
                )
                created_policies.append(policy)
        
        return created_policies

    # ── SLA Timer Management ────────────────────────────────────────────────

    def create_timer(
        self,
        company_id: str,
        ticket_id: str,
        policy_id: str,
    ) -> SLATimer:
        """
        Create an SLA timer for a ticket.
        
        This should be called when a ticket is created.
        """
        policy = self.get_policy(company_id, policy_id)
        if not policy:
            raise SLAPolicyNotFoundError(f"SLA policy {policy_id} not found")
        
        # Check if timer already exists
        existing = self.db.query(SLATimer).filter(
            SLATimer.ticket_id == ticket_id,
        ).first()
        
        if existing:
            return existing
        
        timer = SLATimer(
            ticket_id=ticket_id,
            company_id=company_id,
            policy_id=policy_id,
            is_breached=False,
        )
        self.db.add(timer)
        
        # Update ticket with resolution target
        ticket = self.db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if ticket:
            resolution_target = datetime.utcnow() + timedelta(
                minutes=policy.resolution_minutes
            )
            ticket.resolution_target_at = resolution_target
        
        self.db.commit()
        
        return timer

    def get_timer(
        self,
        company_id: str,
        ticket_id: str,
    ) -> Optional[SLATimer]:
        """Get SLA timer for a ticket."""
        return self.db.query(SLATimer).filter(
            SLATimer.ticket_id == ticket_id,
            SLATimer.company_id == company_id,
        ).first()

    def record_first_response(
        self,
        company_id: str,
        ticket_id: str,
    ) -> Optional[SLATimer]:
        """
        Record first response time for SLA tracking.
        
        Should be called when the first agent/AI response is added.
        """
        timer = self.get_timer(company_id, ticket_id)
        if not timer:
            return None
        
        if timer.first_response_at:
            return timer  # Already recorded
        
        timer.first_response_at = datetime.utcnow()
        timer.updated_at = datetime.utcnow()
        
        # Update ticket
        ticket = self.db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if ticket:
            ticket.first_response_at = timer.first_response_at
        
        # Check if first response SLA was breached
        self._check_first_response_breach(timer)
        
        self.db.commit()
        
        return timer

    def record_resolution(
        self,
        company_id: str,
        ticket_id: str,
    ) -> Optional[SLATimer]:
        """
        Record resolution time for SLA tracking.
        
        Should be called when ticket status changes to 'resolved'.
        """
        timer = self.get_timer(company_id, ticket_id)
        if not timer:
            return None
        
        timer.resolved_at = datetime.utcnow()
        timer.updated_at = datetime.utcnow()
        
        self.db.commit()
        
        return timer

    def _check_first_response_breach(self, timer: SLATimer) -> bool:
        """Check if first response SLA was breached."""
        if not timer.first_response_at:
            return False
        
        policy = self.db.query(SLAPolicy).filter(
            SLAPolicy.id == timer.policy_id,
        ).first()
        
        if not policy:
            return False
        
        # Calculate time to first response
        response_time = (timer.first_response_at - timer.created_at).total_seconds() / 60
        
        if response_time > policy.first_response_minutes:
            timer.breached_at = timer.first_response_at
            timer.is_breached = True
            
            # Update ticket
            ticket = self.db.query(Ticket).filter(
                Ticket.id == timer.ticket_id,
            ).first()
            if ticket:
                ticket.sla_breached = True
            
            return True
        
        return False

    # ── Breach Detection (PS11, PS17) ───────────────────────────────────────

    def check_breach(
        self,
        company_id: str,
        ticket_id: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if SLA has been breached for a ticket.
        
        Returns:
            Tuple of (is_breached, breach_type)
        """
        timer = self.get_timer(company_id, ticket_id)
        if not timer:
            return False, None
        
        if timer.is_breached:
            return True, "already_breached"
        
        if timer.resolved_at:
            return False, None  # Already resolved, no breach check needed
        
        policy = self.db.query(SLAPolicy).filter(
            SLAPolicy.id == timer.policy_id,
        ).first()
        
        if not policy:
            return False, None
        
        now = datetime.utcnow()
        
        # Check first response breach
        if not timer.first_response_at:
            first_response_deadline = timer.created_at + timedelta(
                minutes=policy.first_response_minutes
            )
            if now > first_response_deadline:
                self._mark_breached(timer, "first_response")
                return True, "first_response"
        
        # Check resolution breach
        resolution_deadline = timer.created_at + timedelta(
            minutes=policy.resolution_minutes
        )
        if now > resolution_deadline:
            self._mark_breached(timer, "resolution")
            return True, "resolution"
        
        return False, None

    def _mark_breached(self, timer: SLATimer, breach_type: str) -> None:
        """Mark a timer as breached."""
        timer.is_breached = True
        timer.breached_at = datetime.utcnow()
        timer.updated_at = datetime.utcnow()
        
        # Update ticket
        ticket = self.db.query(Ticket).filter(
            Ticket.id == timer.ticket_id,
        ).first()
        if ticket:
            ticket.sla_breached = True
            # PS11: Escalate priority on breach
            if ticket.priority != Priority.critical.value:
                ticket.priority = Priority.critical.value
        
        self.db.commit()

    def is_approaching_breach(
        self,
        company_id: str,
        ticket_id: str,
    ) -> Tuple[bool, Optional[float]]:
        """
        Check if SLA is approaching breach (PS17: 75% threshold).
        
        Returns:
            Tuple of (is_approaching, percentage_elapsed)
        """
        timer = self.get_timer(company_id, ticket_id)
        if not timer or timer.is_breached or timer.resolved_at:
            return False, None
        
        policy = self.db.query(SLAPolicy).filter(
            SLAPolicy.id == timer.policy_id,
        ).first()
        
        if not policy:
            return False, None
        
        now = datetime.utcnow()
        
        # Calculate elapsed percentage based on resolution time
        total_seconds = policy.resolution_minutes * 60
        elapsed_seconds = (now - timer.created_at).total_seconds()
        
        if total_seconds <= 0:
            return False, None
        
        percentage = elapsed_seconds / total_seconds
        
        return percentage >= self.APPROACHING_THRESHOLD, percentage

    def get_breached_tickets(
        self,
        company_id: str,
        limit: int = 100,
    ) -> List[Ticket]:
        """Get all breached SLA tickets for a company."""
        return self.db.query(Ticket).join(
            SLATimer, Ticket.id == SLATimer.ticket_id
        ).filter(
            Ticket.company_id == company_id,
            SLATimer.is_breached == True,  # noqa: E712
            Ticket.status.notin_([
                TicketStatus.closed.value,
                TicketStatus.resolved.value,
            ]),
        ).order_by(SLATimer.breached_at.desc()).limit(limit).all()

    def get_approaching_tickets(
        self,
        company_id: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get tickets approaching SLA breach (75% threshold).
        
        Returns list of dicts with ticket and percentage info.
        """
        # Get all active timers
        timers = self.db.query(SLATimer).filter(
            SLATimer.company_id == company_id,
            SLATimer.is_breached == False,  # noqa: E712
            SLATimer.resolved_at == None,  # noqa: E711
        ).all()
        
        approaching = []
        for timer in timers:
            is_approaching, percentage = self.is_approaching_breach(
                company_id, timer.ticket_id
            )
            if is_approaching:
                ticket = self.db.query(Ticket).filter(
                    Ticket.id == timer.ticket_id,
                ).first()
                if ticket:
                    approaching.append({
                        "ticket": ticket,
                        "timer": timer,
                        "percentage": percentage,
                    })
        
        # Sort by percentage (highest first)
        approaching.sort(key=lambda x: x["percentage"], reverse=True)
        
        return approaching[:limit]

    # ── SLA Statistics ──────────────────────────────────────────────────────

    def get_sla_stats(
        self,
        company_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get SLA statistics for a company.
        
        Returns:
            Dict with compliance rate, average times, breach counts, etc.
        """
        query = self.db.query(SLATimer).filter(
            SLATimer.company_id == company_id,
        )
        
        if start_date:
            query = query.filter(SLATimer.created_at >= start_date)
        if end_date:
            query = query.filter(SLATimer.created_at <= end_date)
        
        timers = query.all()
        
        if not timers:
            return {
                "total_tickets": 0,
                "breached_count": 0,
                "compliant_count": 0,
                "compliance_rate": 1.0,
                "avg_first_response_minutes": None,
                "avg_resolution_minutes": None,
            }
        
        breached = [t for t in timers if t.is_breached]
        compliant = [t for t in timers if not t.is_breached and t.resolved_at]
        
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
        
        total = len(timers)
        breached_count = len(breached)
        compliant_count = len(compliant)
        
        return {
            "total_tickets": total,
            "breached_count": breached_count,
            "compliant_count": compliant_count,
            "approaching_count": len(self.get_approaching_tickets(company_id)),
            "compliance_rate": compliant_count / total if total > 0 else 1.0,
            "avg_first_response_minutes": (
                sum(first_response_times) / len(first_response_times)
                if first_response_times else None
            ),
            "avg_resolution_minutes": (
                sum(resolution_times) / len(resolution_times)
                if resolution_times else None
            ),
        }
