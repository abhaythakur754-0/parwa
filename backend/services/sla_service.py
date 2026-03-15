"""
SLA (Service Level Agreement) Service Layer.

Handles SLA tracking, breach detection, and reporting.
All methods are company-scoped for RLS compliance.
"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timezone, timedelta
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, desc

from backend.models.sla_breach import SLABreach
from shared.core_functions.logger import get_logger

logger = get_logger(__name__)


class SLATier(str, Enum):
    """SLA tier levels."""
    MINI = "mini"          # 24hr response, 72hr resolution
    PARWA = "parwa"        # 4hr response, 24hr resolution
    PARWA_HIGH = "high"    # 1hr response, 4hr resolution


class BreachPhase(int, Enum):
    """SLA breach phases."""
    PHASE_1 = 1  # First SLA breach warning
    PHASE_2 = 2  # Second escalation
    PHASE_3 = 3  # Critical breach


class SLAConfig:
    """SLA configuration by tier."""
    TIERS = {
        SLATier.MINI: {
            "response_hours": 24,
            "resolution_hours": 72,
            "support_hours": "9am-5pm EST",
            "channels": ["email"],
            "escalation_hours": [12, 24, 48],  # Phases 1, 2, 3
        },
        SLATier.PARWA: {
            "response_hours": 4,
            "resolution_hours": 24,
            "support_hours": "8am-8pm EST",
            "channels": ["email", "chat"],
            "escalation_hours": [2, 4, 12],
        },
        SLATier.PARWA_HIGH: {
            "response_hours": 1,
            "resolution_hours": 4,
            "support_hours": "24/7",
            "channels": ["email", "chat", "phone", "video"],
            "escalation_hours": [0.5, 1, 2],
        },
    }


class SLAService:
    """
    Service class for SLA tracking and breach management.
    
    All methods enforce company-scoped data access (RLS).
    """
    
    def __init__(self, db: AsyncSession, company_id: UUID) -> None:
        """
        Initialize SLA service.
        
        Args:
            db: Async database session
            company_id: Company UUID for RLS scoping
        """
        self.db = db
        self.company_id = company_id
    
    async def get_sla_config(self, tier: SLATier) -> Dict[str, Any]:
        """
        Get SLA configuration for a tier.
        
        Args:
            tier: SLA tier level
            
        Returns:
            Dict with SLA configuration
        """
        return SLAConfig.TIERS.get(tier, SLAConfig.TIERS[SLATier.MINI])
    
    async def check_sla_breach(
        self,
        ticket_id: UUID,
        tier: SLATier,
        created_at: datetime,
        first_response_at: Optional[datetime] = None,
        resolved_at: Optional[datetime] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Check if a ticket has breached SLA.
        
        Args:
            ticket_id: Ticket UUID
            tier: SLA tier
            created_at: When ticket was created
            first_response_at: When first response was made
            resolved_at: When ticket was resolved
            
        Returns:
            Dict with breach details if breached, None otherwise
        """
        config = await self.get_sla_config(tier)
        now = datetime.now(timezone.utc)
        
        response_deadline = created_at + timedelta(hours=config["response_hours"])
        resolution_deadline = created_at + timedelta(hours=config["resolution_hours"])
        
        # Check resolution SLA first (higher priority)
        if resolved_at is None:
            if now > resolution_deadline:
                hours_overdue = (now - resolution_deadline).total_seconds() / 3600
                
                logger.warning({
                    "event": "sla_resolution_breach",
                    "company_id": str(self.company_id),
                    "ticket_id": str(ticket_id),
                    "tier": tier.value,
                    "expected_hours": config["resolution_hours"],
                    "actual_hours": (now - created_at).total_seconds() / 3600,
                    "hours_overdue": hours_overdue,
                })
                
                breach_id = UUID(int=0)  # Placeholder
                return {
                    "breach_id": str(breach_id),
                    "ticket_id": str(ticket_id),
                    "breach_type": "resolution",
                    "tier": tier.value,
                    "deadline": resolution_deadline.isoformat(),
                    "detected_at": now.isoformat(),
                    "hours_overdue": hours_overdue,
                }
        
        # Check response SLA
        if first_response_at is None:
            if now > response_deadline:
                hours_overdue = (now - response_deadline).total_seconds() / 3600
                
                logger.warning({
                    "event": "sla_response_breach",
                    "company_id": str(self.company_id),
                    "ticket_id": str(ticket_id),
                    "tier": tier.value,
                    "expected_hours": config["response_hours"],
                    "actual_hours": (now - created_at).total_seconds() / 3600,
                    "hours_overdue": hours_overdue,
                })
                
                breach_id = UUID(int=0)
                return {
                    "breach_id": str(breach_id),
                    "ticket_id": str(ticket_id),
                    "breach_type": "response",
                    "tier": tier.value,
                    "deadline": response_deadline.isoformat(),
                    "detected_at": now.isoformat(),
                    "hours_overdue": hours_overdue,
                }
        
        return None
    
    async def determine_breach_phase(
        self,
        tier: SLATier,
        hours_overdue: float
    ) -> BreachPhase:
        """
        Determine the breach phase based on hours overdue.
        
        Args:
            tier: SLA tier
            hours_overdue: Number of hours past SLA deadline
            
        Returns:
            BreachPhase enum value
        """
        config = await self.get_sla_config(tier)
        escalation_hours = config.get("escalation_hours", [12, 24, 48])
        
        if hours_overdue >= escalation_hours[2]:
            return BreachPhase.PHASE_3
        elif hours_overdue >= escalation_hours[1]:
            return BreachPhase.PHASE_2
        elif hours_overdue >= escalation_hours[0]:
            return BreachPhase.PHASE_1
        
        return BreachPhase.PHASE_1  # Default to phase 1 if any breach
    
    async def record_breach(
        self,
        ticket_id: UUID,
        breach_phase: BreachPhase,
        hours_overdue: float,
        notified_to: str
    ) -> Dict[str, Any]:
        """
        Record an SLA breach.
        
        Args:
            ticket_id: Ticket UUID
            breach_phase: Phase of the breach (1, 2, or 3)
            hours_overdue: Hours past SLA deadline
            notified_to: Who was notified (email or role)
            
        Returns:
            Dict with breach record details
        """
        breach_id = UUID(int=0)  # Placeholder for actual UUID generation
        now = datetime.now(timezone.utc)
        
        logger.warning({
            "event": "sla_breach_recorded",
            "company_id": str(self.company_id),
            "ticket_id": str(ticket_id),
            "breach_id": str(breach_id),
            "phase": breach_phase.value,
            "hours_overdue": hours_overdue,
            "notified_to": notified_to,
        })
        
        return {
            "breach_id": str(breach_id),
            "company_id": str(self.company_id),
            "ticket_id": str(ticket_id),
            "breach_phase": breach_phase.value,
            "hours_overdue": hours_overdue,
            "notified_to": notified_to,
            "triggered_at": now.isoformat(),
            "resolved_at": None,
        }
    
    async def resolve_breach(
        self,
        breach_id: UUID
    ) -> Dict[str, Any]:
        """
        Mark an SLA breach as resolved.
        
        Args:
            breach_id: UUID of the breach to resolve
            
        Returns:
            Dict with resolution status
        """
        now = datetime.now(timezone.utc)
        
        logger.info({
            "event": "sla_breach_resolved",
            "company_id": str(self.company_id),
            "breach_id": str(breach_id),
            "resolved_at": now.isoformat(),
        })
        
        return {
            "breach_id": str(breach_id),
            "resolved": True,
            "resolved_at": now.isoformat(),
        }
    
    async def get_sla_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get SLA metrics for the company.
        
        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            Dict with SLA metrics
        """
        logger.info({
            "event": "sla_metrics_retrieved",
            "company_id": str(self.company_id),
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        })
        
        # TODO: Query from database when implemented
        return {
            "company_id": str(self.company_id),
            "period": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None,
            },
            "metrics": {
                "total_tickets": 0,
                "response_sla_met": 0,
                "resolution_sla_met": 0,
                "breaches": 0,
                "compliance_rate": 0.0,
                "avg_response_time_hours": 0.0,
                "avg_resolution_time_hours": 0.0,
            },
            "by_tier": {
                SLATier.MINI.value: {"total": 0, "breaches": 0},
                SLATier.PARWA.value: {"total": 0, "breaches": 0},
                SLATier.PARWA_HIGH.value: {"total": 0, "breaches": 0},
            },
        }
    
    async def list_breaches(
        self,
        ticket_id: Optional[UUID] = None,
        breach_phase: Optional[BreachPhase] = None,
        resolved: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List SLA breaches for the company.
        
        Args:
            ticket_id: Filter by ticket
            breach_phase: Filter by breach phase
            resolved: Filter by resolution status
            limit: Max results
            offset: Pagination offset
            
        Returns:
            List of SLA breaches
        """
        logger.info({
            "event": "sla_breaches_listed",
            "company_id": str(self.company_id),
            "filters": {
                "ticket_id": str(ticket_id) if ticket_id else None,
                "breach_phase": breach_phase.value if breach_phase else None,
                "resolved": resolved,
            },
            "limit": limit,
            "offset": offset,
        })
        
        # TODO: Query from database
        return []
    
    async def get_breach_by_id(
        self,
        breach_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Get a specific SLA breach by ID.
        
        Args:
            breach_id: UUID of the breach
            
        Returns:
            Dict with breach details or None
        """
        logger.info({
            "event": "sla_breach_retrieved",
            "company_id": str(self.company_id),
            "breach_id": str(breach_id),
        })
        
        # TODO: Query from database
        return None
    
    async def get_breaches_by_ticket(
        self,
        ticket_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Get all SLA breaches for a specific ticket.
        
        Args:
            ticket_id: Ticket UUID
            
        Returns:
            List of breaches for the ticket
        """
        return await self.list_breaches(ticket_id=ticket_id)
    
    async def calculate_compliance_rate(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> float:
        """
        Calculate SLA compliance rate for a period.
        
        Args:
            start_date: Start of period
            end_date: End of period
            
        Returns:
            Compliance rate as percentage (0-100)
        """
        metrics = await self.get_sla_metrics(start_date, end_date)
        
        total = metrics["metrics"]["total_tickets"]
        if total == 0:
            return 100.0
        
        breaches = metrics["metrics"]["breaches"]
        compliance_rate = ((total - breaches) / total) * 100
        
        return round(compliance_rate, 2)
    
    async def get_escalation_targets(
        self,
        tier: SLATier,
        phase: BreachPhase
    ) -> List[str]:
        """
        Get escalation targets for a breach phase.
        
        Args:
            tier: SLA tier
            phase: Breach phase
            
        Returns:
            List of email addresses/roles to notify
        """
        # Phase 1: Agent
        # Phase 2: Manager
        # Phase 3: Admin + Manager
        escalation_matrix = {
            BreachPhase.PHASE_1: ["agent"],
            BreachPhase.PHASE_2: ["manager"],
            BreachPhase.PHASE_3: ["admin", "manager"],
        }
        
        return escalation_matrix.get(phase, ["agent"])
